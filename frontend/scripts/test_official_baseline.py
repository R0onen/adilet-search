"""Parser regressions: inline links, notes, document scope and chunk coverage."""
import unittest
from build_official_baseline import chunks_of, parse_page


class ParserTests(unittest.TestCase):
    def page(self, lang='ru'):
        marker = 'Статья {}. Заголовок' if lang == 'ru' else '{}-бап. Тақырып'
        units = ''.join(
            f'<p><b><a name="z{i}"></a>{marker.format(i)}</b></p>'
            '<p>1. До <a href="/source">ссылки</a> и после.</p>'
            '<span class="note">Сноска. Закон </span><a href="/law">№ 42</a>'
            '<span class="note"> (вводится позже).</span>'
            for i in range(1, 101)
        )
        return ('<h1>Official title</h1><nav>Navigation</nav><article><h3>Глава 1</h3>'
                + units + '</article><footer><p>Footer</p></footer>').encode()

    def test_inline_text_and_complete_amendment_note(self):
        title, rows = parse_page(self.page(), 'ru')
        self.assertEqual(title, 'Official title')
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]['paragraphs'], ['1. До ссылки и после.'])
        self.assertEqual(' '.join(rows[0]['notes']), 'Сноска. Закон № 42 (вводится позже).')
        self.assertEqual(rows[0]['anchor'], 'z1')
        self.assertEqual(rows[-1]['paragraphs'], ['1. До ссылки и после.'])
        self.assertEqual(rows[0]['chapter'], 'Глава 1')

    def test_kazakh_markers(self):
        html = self.page('kk').replace(b'<p><b>', b'<h3>').replace(b'</b></p>', b'</h3>')
        _, rows = parse_page(html, 'kk')
        self.assertEqual(rows[-1]['number'], '100')

    def test_reject_error_and_duplicate_pages(self):
        with self.assertRaises(ValueError):
            parse_page(b'<h1>Access denied</h1>', 'ru')
        duplicate = self.page().replace(b'</article>', '<p><b>Статья 1. Duplicate</b></p></article>'.encode())
        with self.assertRaises(ValueError):
            parse_page(duplicate, 'ru')

    def test_long_paragraph_preserves_every_character(self):
        text = ' '.join(f'word{i:05d}' for i in range(1900)) + ' END'
        parts = list(chunks_of(text))
        self.assertTrue(all(part in text and len(part) <= 1400 for part in parts))
        # Rebuild through known overlap; catches gaps or dropped long paragraphs.
        rebuilt = parts[0]
        for part in parts[1:]:
            overlap = next(n for n in range(min(len(rebuilt), len(part)), 0, -1) if rebuilt.endswith(part[:n]))
            rebuilt += part[overlap:]
        self.assertEqual(rebuilt, text)


if __name__ == '__main__':
    unittest.main()
