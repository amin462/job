"""How many O*NET 'Workplace Example' software names appear in the sampled Thai postings?"""
import glob, os, re, sys
from collections import Counter
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_jobposting import extract
from analyze_sample import clean

onet = pd.read_csv(sys.argv[1])
hot = onet[onet["Hot Technology"] == "Y"]["Workplace Example"].dropna().unique()
names = [n for n in hot if len(n) >= 4]
rx = {n: re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", re.I) for n in names}
texts = []
for d in sys.argv[2:]:
    for f in glob.glob(os.path.join(d, "job_*.html")):
        r = extract(f)
        if r:
            texts.append(f"{r.get('title','')} {clean(r.get('description'))} {clean(r.get('qualifications'))}")
hits = Counter()
per_post = []
for t in texts:
    found = {n for n, r in rx.items() if r.search(t)}
    hits.update(found); per_post.append(len(found))
print(f"O*NET hot-technology names: {len(names)} | postings: {len(texts)}")
print(f"postings with >=1 O*NET software name: {sum(1 for x in per_post if x)}/{len(texts)}")
print("top:", dict(hits.most_common(12)))
