"""Inspect legacy notebook source without executing cells or loading any dataset."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def audit(path):
    raw = path.read_bytes()
    notebook = json.loads(raw)
    cells = []
    lists = {}
    for number, cell in enumerate(notebook['cells'], 1):
        source = ''.join(cell.get('source', []))
        if cell['cell_type'] == 'code':
            tree = ast.parse(source, filename=f'{path}:cell-{number}')
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ('drop_columns', 'categorical_cols'):
                            lists[target.id] = ast.literal_eval(node.value)
        cells.append({'number': number, 'type': cell['cell_type'],
                      'source_lines': len(source.splitlines()),
                      'saved_outputs': len(cell.get('outputs', [])),
                      'execution_count': cell.get('execution_count')})
    return {'notebook': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
            'inspection_only': True, 'dataset_loaded': False, 'cells': cells,
            'declared_lists': lists,
            'feature_matrix': 'dynamic: all surviving columns except both targets; CSV required for exact schema'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook', type=Path, default=Path('src/classifier/iot-test.ipynb'))
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    result = audit(args.notebook)
    if args.expected_sha256 and result['sha256'] != args.expected_sha256:
        parser.error('Notebook differs from the expected baseline')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
