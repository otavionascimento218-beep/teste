"""Run reproducible adaptive responses against all 180 illustrative items."""
import argparse
import json
import time
import numpy as np
from .engine import probability, recommendations

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=180)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--responses', help='JSON list of {question_id, option}; evaluated in adaptive order')
    args = parser.parse_args()
    if not 1 <= args.steps <= 180:
        parser.error('--steps deve estar entre 1 e 180')
    supplied = None
    if args.responses:
        with open(args.responses, encoding='utf-8') as file:
            supplied = json.load(file)
        if not isinstance(supplied, list):
            parser.error('respostas devem ser uma lista')
    history, rng = [], np.random.default_rng(args.seed)
    true_theta = np.array([.8, .4, .2, -.1])
    for n in range(args.steps):
        item, theta, sd, levels, f = recommendations(history)
        if item is None:
            print(json.dumps({'status': 'no_eligible_item', 'answered': len(history),
                              'reason': 'Banco esgotado ou pré-requisitos pendentes.'}, ensure_ascii=False))
            break
        if supplied is not None:
            if n >= len(supplied):
                break
            row = supplied[n]
            if not isinstance(row, dict) or row.get('question_id') != item.id or type(row.get('option')) is not int or not 0 <= row['option'] < 5:
                parser.error(f'resposta {n+1}: esperado question_id={item.id} e option inteiro entre 0 e 4')
            correct = row['option'] == item.answer
        else:
            correct = bool(rng.random() < probability(item, true_theta[item.area_index]))
        history.append({'question_id': item.id, 'correct': int(correct), 'reaction_seconds': float(rng.uniform(20,70)),
                        'predicted_probability': float(probability(item, theta[item.area_index])),
                        'created_at': time.time()+n, 'confidence': .5})
        next_item, updated, uncertainty, *_ = recommendations(history)
        print(json.dumps({'iteration': n+1, 'question_id': item.id, 'correct': correct,
                          'theta': np.round(updated, 3).tolist(), 'sd': np.round(uncertainty, 3).tolist(),
                          'next_question_id': next_item.id if next_item else None}, ensure_ascii=False))

if __name__ == '__main__':
    main()
