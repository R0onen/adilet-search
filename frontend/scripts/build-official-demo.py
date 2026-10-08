"""Runtime-only official demo corpus; leaves the committed sample unchanged."""
import hashlib
import json
import re
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup
from adilet_ml.data.sample_builder import DOCUMENT_SCHEMA, ARTICLE_SCHEMA, CHUNK_SCHEMA
from adilet_ml.chunking.chunker import embedding_header, iter_text_chunks

out = Path('/tmp/official-demo')
out.mkdir(exist_ok=True)
docs, articles, chunks, provenance = [], [], [], []
for lang, prefix in [('ru', 'rus'), ('kk', 'kaz')]:
    url = f'https://old.adilet.zan.kz/{prefix}/docs/K1500000414'
    raw_path = Path(f'/tmp/labor-{lang}.html')
    if not raw_path.exists():
        raw_path.write_bytes(urllib.request.urlopen(url, timeout=45).read())
    raw = raw_path.read_bytes()
    soup = BeautifulSoup(raw, 'html.parser')
    title = soup.find('h1').get_text(' ', strip=True)
    short = title + ' [3-article demo snapshot]'
    provenance.append({'lang':lang, 'url':url, 'fetched_at':datetime.now(UTC).isoformat(), 'html_sha256':hashlib.sha256(raw).hexdigest()})
    for order, number in enumerate(['68', '88', '113']):
        heading = next(p for p in soup.find_all('p') if p.get_text(' ',strip=True).startswith(f'Статья {number}.') if lang == 'ru') if lang == 'ru' else next(p for p in soup.find_all('p') if p.get_text(' ',strip=True).startswith(f'{number}-бап.'))
        heading_text = heading.get_text(' ',strip=True)
        unit_title = heading_text.split('.',1)[1].strip()
        paragraphs, notes = [], []
        in_note = False
        for sibling in heading.next_siblings:
            if not getattr(sibling,'name',None):
                continue
            text = sibling.get_text(' ',strip=True)
            if re.match(r'^(Статья\s+\d|\d+(?:-\d+)?-бап)', text):
                break
            if not text:
                continue
            if sibling.name == 'p':
                in_note = False
            if text.startswith(('Сноска.', 'Ескерту.')):
                in_note = True
            if in_note:
                notes.append(text)
            else:
                paragraphs.append(text)
        text = '\n'.join(paragraphs)
        assert len(text) > 80, (lang, number)
        anchor = heading.find('a', attrs={'name':True})
        source = url + ('#' + anchor['name'] if anchor else '')
        row = dict(article_id=f'K1500000414:{lang}:a{number}',doc_id='K1500000414',lang=lang,unit_type='article',unit_key=f'a{number}',unit_number=number,unit_title=unit_title,unit_order=order,unit_status='in_force',section_title=None,chapter_title=None,has_amendments=bool(notes),source_url=source,parallel_article_id=f'K1500000414:{"kk" if lang=="ru" else "ru"}:a{number}',content_hash=hashlib.sha256(text.encode()).hexdigest(),text=text,amendment_notes=notes)
        articles.append(row)
        parts = list(iter_text_chunks(text, max_tokens=400))
        for idx, part in enumerate(parts):
            chunk = {k:v for k,v in row.items() if k not in ('text','amendment_notes')}
            chunk.update(chunk_id=f'{row["article_id"]}:c{idx}',chunk_index=idx,chunk_count=len(parts),text=part,text_for_embedding=embedding_header(short,number,unit_title,lang)+'\n'+part,doc_title=title,doc_short_title=short,doc_type='code',doc_status='in_force',adopted_date=date(2015,11,23),revision_date=None,char_len=len(part),token_len=len(part.split()),chunking_version='ch1',corpus_version='2026.10.08-official-demo')
            chunks.append(chunk)
    docs.append(dict(doc_id='K1500000414',lang=lang,title=title,short_title=short,doc_type='code',number='414-V',adopted_date=date(2015,11,23),revision_date=None,status='in_force',source_url=url,article_count=3,scraped_at=datetime.now(UTC),corpus_version='2026.10.08-official-demo'))
for name, rows, schema in [('documents',docs,DOCUMENT_SCHEMA),('articles',articles,ARTICLE_SCHEMA),('chunks',chunks,CHUNK_SCHEMA)]:
    pq.write_table(pa.Table.from_pylist(rows,schema=schema),out/f'{name}.parquet')
(out/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
(out/'articles.json').write_text(json.dumps(articles,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'documents':len(docs),'articles':len(articles),'chunks':len(chunks),'titles':[(a['lang'],a['unit_number'],a['unit_title']) for a in articles]},ensure_ascii=False))
