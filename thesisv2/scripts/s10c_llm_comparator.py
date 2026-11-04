"""Step 10c (optional, GPU): an open instruction-tuned language model chooses five tags from the vocabulary for each description of the 106 set and the
Pakistan 528 (post hoc comparator; the test split is not touched). Model and 4-bit loading follow pk_extension/colab_score_extended.py (Qwen2.5-7B-Instruct).
Hits@1/3/5 use the order the model returns; answers outside the vocabulary count as misses."""
from v2lib import *


def main():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    assert torch.cuda.is_available(), 'GPU runtime needed'
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]; alias = alias_map(); fix = lambda t: alias.get(t, t)
    r106, _ = load_106(); X, ids528, _, _ = load_pk(); byid = {r['id']: r for r in X}
    items = {'eval_106': [(r['sentence'], fix(r['gold_tag'])) for r in r106], 'pk528': [(byid[i]['sentence'], fix(byid[i]['gold_tag'])) for i in ids528]}
    if SMOKE: items = {k: v[:6] for k, v in items.items()}
    mid = 'Qwen/Qwen2.5-7B-Instruct'; tok = AutoTokenizer.from_pretrained(mid); tok.padding_side = 'left'
    model = AutoModelForCausalLM.from_pretrained(mid, quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type='nf4'), device_map='auto').eval()
    vocab = ', '.join(lex); norm = {t.lower(): t for t in lex}
    sysmsg = 'You label places. Given a description that never names the place type, choose the five most likely OpenStreetMap tags from the allowed list, most likely first. Answer with five tags from the list, one per line, nothing else.'
    out = {}
    for s, rows in items.items():
        res = []
        for i in range(0, len(rows), 8):
            batch = rows[i:i + 8]
            msgs = [[{'role': 'system', 'content': sysmsg}, {'role': 'user', 'content': f'Allowed tags: {vocab}\n\nDescription: {t}'}] for t, _ in batch]
            enc = tok([tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in msgs], return_tensors='pt', padding=True).to('cuda')
            with torch.no_grad(): gen = model.generate(**enc, max_new_tokens=40, do_sample=False)
            for (t, g), o in zip(batch, tok.batch_decode(gen[:, enc.input_ids.shape[1]:], skip_special_tokens=True)):
                ans = [norm[a.strip().lower().lstrip('-* 0123456789.')] for a in o.split('\n') if a.strip().lower().lstrip('-* 0123456789.') in norm][:5]
                res.append({'gold': g, 'answer': ans, 'rank': ans.index(g) + 1 if g in ans else 99})
        r = np.array([x['rank'] for x in res]); out[s] = {'n': len(r), **{f'Hits@{k}': float((r <= k).mean()) for k in (1, 3, 5)}, 'rows': res}
        print(s, {k: v for k, v in out[s].items() if k != 'rows'})
    out['model'] = mid; jdump(out, P('results', 's10c_llm_comparator.json')); manifest('s10c', [P('protocol', 'lexicon_v2.txt')], [P('results', 's10c_llm_comparator.json')])


if __name__ == '__main__': main()
