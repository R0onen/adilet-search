"""Build a cached official RU/KK baseline using the existing ML-container dependencies.

Run with --help. Does not modify the committed bootstrap corpus or models.
"""
import argparse
import hashlib
import json
import re
import time
import urllib.request
import urllib.robotparser
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup
from adilet_ml.data.schema import DOCUMENT_SCHEMA, ARTICLE_SCHEMA, CHUNK_SCHEMA
from adilet_ml.chunking.chunker import embedding_header

HOST = 'https://old.adilet.zan.kz'
AGENT = 'AdiletSearchCourseProject/0.1 (educational cached corpus)'
ACTS = [
    ('K1500000414', '414-V', date(2015, 11, 23), 'Трудовой кодекс РК', 'ҚР Еңбек кодексі'),
    ('K2100000400', '400-VI', date(2021, 1, 2), 'Экологический кодекс РК', 'ҚР Экологиялық кодексі'),
]
MARKERS = {
    'ru': re.compile(r'^Статья\s+(\d+(?:-\d+)?)\.?\s*(.*)$'),
    'kk': re.compile(r'^(\d+(?:-\d+)?)-бап\.?\s*(.*)$'),
}


def chunks_of(text, limit=1400, overlap=180):
    """Bounded, overlapping exact slices; never drop an oversized paragraph."""
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind(' ', start + limit // 2, end)
            if boundary > start:
                end = boundary
        yield text[start:end]
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
        boundary = text.find(' ', start, end)
        if boundary != -1:
            start = boundary + 1


def parse_page(raw, lang):
    soup = BeautifulSoup(raw, 'html.parser')
    title = soup.find('h1')
    body = soup.find('article')
    if title is None or body is None:
        raise ValueError('Missing official title/article container (possibly an error page)')
    rows, current, note_mode = [], None, False
    section, chapter = None, None
    for node in body.children:
        if not getattr(node, 'name', None):
            continue
        visible = node.get_text('', strip=False).strip()
        heading_text = re.sub(r'\s+', ' ', visible).strip()
        match = MARKERS[lang].match(heading_text) if node.name in ('h2', 'h3', 'h4') or (node.name == 'p' and node.find('b')) else None
        if node.name.startswith('h') and not match:
            if re.search(r'Глава|тарау', heading_text, re.I):
                chapter = heading_text
            elif re.search(r'РАЗДЕЛ|БӨЛІМ', heading_text, re.I):
                section, chapter = heading_text, None
            continue
        if match:
            anchor = node.find('a', attrs={'name': True})
            current = dict(number=match[1], title=match[2], anchor=anchor['name'] if anchor else node.get('id'), paragraphs=[], notes=[], section=section, chapter=chapter)
            rows.append(current)
            note_mode = False
            continue
        if current is None or not visible:
            continue
        if node.name == 'p':
            note_mode = False
        if 'note' in node.get('class', []) or heading_text.startswith(('Сноска.', 'Ескерту.')):
            note_mode = True
        if note_mode:
            current['notes'].append(visible)
        elif node.name == 'p' and not node.find('table'):
            current['paragraphs'].append(visible)
    if len(rows) < 100:
        raise ValueError(f'Suspiciously incomplete source: only {len(rows)} articles')
    numbers = [row['number'] for row in rows]
    if len(numbers) != len(set(numbers)):
        raise ValueError('Duplicate article markers; refusing ambiguous extraction')
    return title.get_text(' ', strip=True), rows


def fetch_cached(url, cache, robots):
    if cache.exists():
        return cache.read_bytes()
    if robots is None:
        raise ValueError(f'Offline mode requires a cached page: {cache}')
    if not robots.can_fetch(AGENT, url):
        raise ValueError(f'robots.txt disallows {url}')
    cache.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        time.sleep(1 + attempt * 2)
        try:
            request = urllib.request.Request(url, headers={'User-Agent': AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
            if len(raw) < 10000:
                raise ValueError('Response too small for a full code')
            cache.write_bytes(raw)
            cache.with_suffix('.fetched_at').write_text(datetime.now(UTC).isoformat())
            return raw
        except (OSError, ValueError):
            if attempt == 2:
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=Path('/tmp/official-baseline'))
    parser.add_argument('--offline', action='store_true', help='Reparse cached pages without any network requests')
    args = parser.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    robots = None
    if not args.offline:
        robots = urllib.robotparser.RobotFileParser(HOST + '/robots.txt')
        robots.read()
    version = '2026.10.08-official-baseline'
    documents, articles, chunks, provenance, issues = [], [], [], [], []
    for doc_id, doc_number, adopted, short_ru, short_kk in ACTS:
        for lang, prefix, short in [('ru', 'rus', short_ru), ('kk', 'kaz', short_kk)]:
            url = f'{HOST}/{prefix}/docs/{doc_id}'
            cache = out / 'raw' / lang / f'{doc_id}.html'
            raw = fetch_cached(url, cache, robots)
            title, parsed = parse_page(raw, lang)
            fetched = cache.with_suffix('.fetched_at').read_text().strip()
            provenance.append(dict(doc_id=doc_id, lang=lang, url=url, fetched_at=fetched, html_sha256=hashlib.sha256(raw).hexdigest(), articles=len(parsed)))
            documents.append(dict(doc_id=doc_id, lang=lang, title=title, short_title=short, doc_type='code', number=doc_number, adopted_date=adopted, revision_date=None, status='in_force', source_url=url, article_count=len(parsed), scraped_at=datetime.fromisoformat(fetched), corpus_version=version))
            for order, item in enumerate(parsed):
                number = item['number']
                text = '\n'.join(item['paragraphs'])
                notes_text = ' '.join(item['notes'])
                excluded = bool(re.match(r'^(Исключен[ао]?|Алып тастал)', item['title'], re.I)) or bool(re.match(r'^(Исключен[ао]?|Алып тастал)', text, re.I)) or bool(re.search(rf'(?:Стать[яю]\s+{re.escape(number)}\s+исключ|{re.escape(number)}-бап\s+алып\s+тастал)', notes_text, re.I))
                if not text:
                    issues.append(dict(doc_id=doc_id, lang=lang, article=number, issue='empty_body', excluded=excluded))
                    if not excluded:
                        raise ValueError(f'Unexplained empty article: {doc_id}/{lang}/{number}')
                    text = notes_text
                article = dict(article_id=f'{doc_id}:{lang}:a{number}',doc_id=doc_id,lang=lang,unit_type='article',unit_key=f'a{number}',unit_number=number,unit_title=item['title'],unit_order=order,unit_status='excluded' if excluded else 'in_force',section_title=item['section'],chapter_title=item['chapter'],has_amendments=bool(item['notes']),source_url=url+('#'+item['anchor'] if item['anchor'] else ''),parallel_article_id=f'{doc_id}:{"kk" if lang=="ru" else "ru"}:a{number}',content_hash=hashlib.sha256(text.encode()).hexdigest(),text=text,amendment_notes=[' '.join(item['notes'])] if item['notes'] else [])
                articles.append(article)
                parts = list(chunks_of(text))
                for idx, part in enumerate(parts):
                    assert part in text and len(part) <= 1400
                    chunk = {key:value for key,value in article.items() if key not in ('text','amendment_notes')}
                    chunk.update(chunk_id=f'{article["article_id"]}:c{idx}',chunk_index=idx,chunk_count=len(parts),text=part,text_for_embedding=embedding_header(short,number,item['title'],lang)+'\n'+part,doc_title=title,doc_short_title=short,doc_type='code',doc_status='in_force',adopted_date=adopted,revision_date=None,char_len=len(part),token_len=len(part.split()),chunking_version='demo-char1400-v1',corpus_version=version)
                    chunks.append(chunk)
            print(json.dumps(provenance[-1],ensure_ascii=False),flush=True)
    ids = {article['article_id'] for article in articles}
    for row in articles + chunks:
        if row['parallel_article_id'] not in ids:
            row['parallel_article_id'] = None
    for name, rows, schema in [('documents',documents,DOCUMENT_SCHEMA),('articles',articles,ARTICLE_SCHEMA),('chunks',chunks,CHUNK_SCHEMA)]:
        pq.write_table(pa.Table.from_pylist(rows,schema=schema),out/f'{name}.parquet')
    quality = dict(documents=len(documents),articles=len(articles),chunks=len(chunks),excluded=sum(a['unit_status']=='excluded' for a in articles),issues=issues,corpus_version=version,chunking=dict(version='demo-char1400-v1',max_chars=1400,overlap_chars=180),revision_dates='unknown; not inferred from retrieval date',legal_status='code-level in_force; amendment effective-date resolution requires review')
    for name, data in [('provenance',provenance),('quality',quality),('articles',articles)]:
        (out/f'{name}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(quality,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
