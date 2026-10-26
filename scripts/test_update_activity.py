import unittest
from datetime import date, timedelta
from xml.etree import ElementTree

from update_activity import CalendarParser, select_window, render_svg, update_readme


class ActivityTests(unittest.TestCase):
    def test_count_labels_and_zero(self):
        parser = CalendarParser()
        parser.feed('''<td id="a" data-date="2026-10-25" data-level="0"></td>
        <tool-tip for="a">No contributions on October 25th.</tool-tip>
        <td id="b" data-date="2026-10-26" data-level="4"></td>
        <tool-tip for="b">1,234 contributions on October 26th.</tool-tip>''')
        self.assertEqual(parser.counts(), {date(2026, 10, 25): (0, 0), date(2026, 10, 26): (1234, 4)})

    def test_missing_label_fails_instead_of_reporting_zero(self):
        parser = CalendarParser()
        parser.feed('<td id="a" data-date="2026-10-26" data-level="0"></td>')
        with self.assertRaises(ValueError):
            parser.counts()

    def test_60_days_across_year_boundary_and_incomplete_calendar(self):
        end = date(2027, 1, 15)
        counts = {end - timedelta(days=i): (1, 1) for i in range(100)}
        counts[end + timedelta(days=1)] = (100, 4)
        days = select_window(counts, end)
        self.assertEqual(len(days), 60)
        self.assertEqual(days[0][0], date(2026, 11, 17))
        self.assertEqual(days[-1][0], end)
        del counts[end]
        with self.assertRaises(ValueError):
            select_window(counts, end)

    def test_svg_and_readme_refresh_preserve_profile(self):
        end = date(2026, 10, 26)
        days = select_window({end - timedelta(days=i): (0, 0) for i in range(60)}, end)
        root = ElementTree.fromstring(render_svg(days))
        self.assertEqual(len(root.findall('.//{http://www.w3.org/2000/svg}rect[{http://www.w3.org/2000/svg}title]')), 60)
        labels = [node.get('x') for node in root.findall('{http://www.w3.org/2000/svg}text') if node.get('y') == '53']
        self.assertEqual(len(labels), len(set(labels)))
        original = '# Profile\n\n## Products I work on\n\nExisting portfolio.\n'
        updated = update_readme(original, days)
        self.assertEqual(update_readme(updated, days), updated)
        self.assertTrue(updated.endswith('Existing portfolio.\n'))


if __name__ == '__main__':
    unittest.main()
