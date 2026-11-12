import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from identifiers import make_component_id, make_dataset_id, make_mixture_id, make_record_id
from pipeline import load_catalog, parse_document, write_points_csv
from reader import load_json


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.data = load_json(Path(__file__).parent / 'data/j.fluid.2004.02.021.json')
        self.source = 'journal/10.1016/j.fluid.2004.02.021.json'
        self.block = self.data['PureOrMixtureData'][3]
        self.dataset_id = sha(f'{self.source}:4')

    def test_paths_and_hashes(self):
        self.assertEqual(make_dataset_id(self.source.replace('/', '\\'), 4), self.dataset_id)
        self.assertNotEqual(make_dataset_id('another/' + self.source, 4), self.dataset_id)
        for bad in ('../file.json', '/archive/file.json', 'C:/file.json'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                make_dataset_id(bad, 4)
        self.assertEqual(make_record_id(self.dataset_id, 2), sha(f'{self.dataset_id}:2'))
        self.assertEqual(make_mixture_id(['Z', 'A']), sha('A;Z'))

    def test_component_identifiers(self):
        compound = self.data['Compound'][0].copy()
        self.assertEqual(make_component_id(compound), compound.pop('sStandardInChIKey'))
        self.assertEqual(make_component_id(compound), sha(compound.pop('sStandardInChI')))
        self.assertEqual(make_component_id(compound), 'UNRESOLVED_' + sha('1,1,2,2-tetrachloroethaneC2H2Cl4'))

    def test_real_json_and_source_order(self):
        points = parse_document(self.data, self.source, 4)
        self.assertEqual(len(points), 99)
        self.assertEqual([p['point_number'] for p in points], list(range(1, 100)))
        self.assertEqual(points[0]['record_id'], sha(f'{self.dataset_id}:1'))
        self.block['Component'].reverse()
        self.assertEqual(parse_document(self.data, self.source, 4), points)

    def test_catalog_links_and_csv(self):
        baseline = parse_document(self.data, self.source, 4)
        ids = {str(c['RegNum']['nOrgNum']): c['sStandardInChIKey'] for c in self.data['Compound']}
        orgs = [str(c['RegNum']['nOrgNum']) for c in self.block['Component']]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'datasets.csv').write_text(
                f'source_file;data_block;dataset_id;doi\n{self.source};4;{self.dataset_id};wrong\n',
                encoding='utf-8-sig')
            links = directory / 'dataset_components.csv'
            header = 'dataset_id;local_org_num;component_id;original_position\n'
            rows = [f'{self.dataset_id};{org};{ids[org]};{i}\n' for i, org in enumerate(orgs, 1)]
            links.write_text(header + ''.join(reversed(rows)), encoding='utf-8-sig')
            points = parse_document(self.data, self.source, 4, load_catalog(directory))
            self.assertEqual(points, [dict(p, catalog_matched=True) for p in baseline])
            output = directory / 'points.csv'
            write_points_csv(output, points)
            self.assertTrue(output.read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertIn('"Liquid;Gas"', output.read_text(encoding='utf-8-sig'))
            with output.open(encoding='utf-8-sig', newline='') as stream:
                first = next(csv.DictReader(stream, delimiter=';'))
            self.assertEqual(first['phases'], 'Liquid;Gas')
            self.assertEqual(first['component_ids'], ';'.join(points[0]['component_ids']))
            self.assertEqual(json.loads(first['origins']), points[0]['origins'])
            links.write_text(header + rows[0], encoding='utf-8-sig')
            with self.assertRaises(ValueError):
                parse_document(self.data, self.source, 4, load_catalog(directory))

    def test_normalizes_each_phase_independently(self):
        from composition import apply_composition

        point = {'x_by_orgnum': {2: 0.2}, 'y_by_orgnum': {1: 0.3}, 'origins': {}}
        apply_composition(point, [1, 2], {'1': 'A', '2': 'Z'})
        self.assertAlmostEqual(point['x1'], 0.8)
        self.assertAlmostEqual(point['y1'], 0.3)
        self.assertAlmostEqual(point['y2'], 0.7)
        self.assertEqual(point['origins']['x1'], ['derived: 1 - x2'])
