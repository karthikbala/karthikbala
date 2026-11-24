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

    def test_90_days_across_year_boundary_and_incomplete_calendar(self):
        end = date(2027, 1, 15)
        counts = {end - timedelta(days=i): (1, 1) for i in range(100)}
        counts[end + timedelta(days=1)] = (100, 4)
        days = select_window(counts, end)
        self.assertEqual(len(days), 90)
        self.assertEqual(days[0][0], date(2026, 10, 18))
        self.assertEqual(days[-1][0], end)
        del counts[end]
        with self.assertRaises(ValueError):
            select_window(counts, end)

    def test_svg_and_readme_refresh_preserve_profile(self):
        end = date(2027, 1, 1)
        days = select_window({end - timedelta(days=i): (0, 0) for i in range(90)}, end)
        root = ElementTree.fromstring(render_svg(days))
        namespaces = {'svg': 'http://www.w3.org/2000/svg'}
        day_titles = root.findall('svg:rect/svg:title', namespaces)
        self.assertEqual(len(day_titles), 90)
        self.assertEqual(day_titles[0].text, '2026-10-04: 0 contributions')
        self.assertEqual(day_titles[-1].text, '2027-01-01: 0 contributions')
        self.assertEqual(root.find('svg:text[@y="63"]', namespaces).text, '04 Oct 2026 – 01 Jan 2027 · UTC')
        labels = [int(node.get('x')) for node in root.findall('svg:text[@y="53"]', namespaces)]
        self.assertGreaterEqual(min(right - left for left, right in zip(labels, labels[1:])), 44)
        original = '# Profile\n\n## Products I work on\n\nExisting portfolio.\n'
        updated = update_readme(original, days)
        self.assertIn('## Last 90 days', updated)
        self.assertIn('![0 GitHub contributions across 0 active days over the last 90 days](assets/activity-90-days.svg)', updated)
        self.assertEqual(update_readme(updated, days), updated)
        self.assertTrue(updated.startswith('# Profile\n\n'))
        self.assertTrue(updated.endswith('Existing portfolio.\n'))


if __name__ == '__main__':
    unittest.main()
