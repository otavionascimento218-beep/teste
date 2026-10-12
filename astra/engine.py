"""Sequential grid posterior for four independent, illustrative 3PL scales."""
import math
import time
from datetime import datetime, timezone
import numpy as np
from .bank import BANK, CONCEPTS

GRID = np.linspace(-4, 4, 161)
PRIOR = np.exp(-.5 * GRID**2)
PRIOR /= PRIOR.sum()

def probability(item, theta):
    z = np.clip(item.a * (np.asarray(theta) - item.difficulty), -50, 50)
    return item.c + (1-item.c) / (1+np.exp(-z))

def posterior(history):
    logs = np.tile(np.log(PRIOR), (4, 1))
    from .bank import BY_ID
    for response in history:
        q = BY_ID[response['question_id']]
        p = probability(q, GRID)
        logs[q.area_index] += np.log(p if response['correct'] else 1-p)
    logs -= logs.max(axis=1, keepdims=True)
    weights = np.exp(logs)
    weights /= weights.sum(axis=1, keepdims=True)
    theta = weights @ GRID
    sd = np.sqrt((weights * (GRID[None, :] - theta[:, None])**2).sum(axis=1))
    return weights, theta, sd

def mastery(history):
    """Beta mean is an operational evidence index, not validated concept mastery."""
    values = {key: [1., 1.] for key in CONCEPTS}
    from .bank import BY_ID
    for row in history:
        key = BY_ID[row['question_id']].concept
        values[key][0 if row['correct'] else 1] += 1
    return {key: a/(a+b) for key, (a,b) in values.items()}

def fatigue(history):
    """Heuristic session proxy. Device, disability, breaks and item difficulty confound it."""
    if len(history) < 6:
        return 0.
    last = history[-1]['created_at']
    session = [r for r in history if last-r['created_at'] < 3600]
    if len(session) < 6:
        return 0.
    from .bank import BY_ID
    # Use within-area baseline where possible; winsorize delays to avoid idle clicks.
    baseline = session[:-4]
    recent = session[-4:]
    ratios = []
    for row in recent:
        peers = [r for r in baseline if BY_ID[r['question_id']].area_index == BY_ID[row['question_id']].area_index]
        if len(peers) >= 3:
            base = np.median([max(1., min(300., r['reaction_seconds'])) for r in peers])
            ratios.append(math.log(max(1., min(300., row['reaction_seconds']))/base))
    slowing = max(0., float(np.median(ratios))) if ratios else 0.
    # Residuals use pre-response prediction persisted with each attempt.
    residual = np.mean([r['predicted_probability']-r['correct'] for r in recent])
    strain = .7*slowing + .8*max(0., float(residual)-.15)
    return float(np.clip(1-math.exp(-strain), 0, 1))

def recommendations(history):
    weights, theta, sd = posterior(history)
    levels = mastery(history)
    f = fatigue(history)
    answered = {r['question_id'] for r in history}
    counts = np.bincount([int(r['question_id'][0])-1 for r in history], minlength=4)
    best = None
    target = .70 + .15*f
    due_concepts = {r['concept'] for r in review_schedule(history)
                    if datetime.fromisoformat(r['due_at']).timestamp() <= time.time()}
    for item in BANK:
        if item.id in answered:
            continue
        prerequisites = CONCEPTS[item.concept][2]
        if item.difficulty > .5 and any(levels[p] < .65 for p in prerequisites):
            continue
        p = probability(item, GRID)
        logistic = (p-item.c)/(1-item.c)
        derivative = item.a*(1-item.c)*logistic*(1-logistic)
        information = derivative**2 / (p*(1-p))
        expected_p = float(weights[item.area_index] @ p)
        expected_info = float(weights[item.area_index] @ information)
        balance = .20*(float(counts.max())-counts[item.area_index])
        review_bonus = .25 if item.concept in due_concepts else 0.
        utility = expected_info - 2.*abs(expected_p-target) + balance + .15*(1-levels[item.concept]) + review_bonus
        if best is None or utility > best[0]:
            best = (utility, item, expected_p)
    return (best[1] if best else None), theta, sd, levels, f

def review_schedule(history):
    from .bank import BY_ID
    grouped = {}
    for row in history:
        grouped.setdefault(BY_ID[row['question_id']].concept, []).append(row)
    result = []
    for concept, rows in grouped.items():
        stability = 1.
        for row in rows:
            stability = min(60., stability*1.7) if row['correct'] else max(.25, stability*.4)
        # R(t)=exp(-t/S), due when retention estimate reaches .8.
        interval = max(.1, -stability*math.log(.8))
        due = rows[-1]['created_at'] + interval*86400
        result.append({'concept': concept, 'label': CONCEPTS[concept][0],
                       'due_at': datetime.fromtimestamp(due, timezone.utc).isoformat(),
                       'interval_days': round(interval, 2)})
    return sorted(result, key=lambda r: r['due_at'])
