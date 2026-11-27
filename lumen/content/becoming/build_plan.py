#!/usr/bin/env python3
"""Convert pathway-becoming.md into the BECOMING_PLAN Python literal.

The markdown is the authored source; this keeps server.py in sync with it
without anyone retyping nine lessons. The Grounding citations are dropped and
replaced by PRINCIPLES — the pathway speaks from its own position rather than
borrowing authority from studies.
"""
import re, pprint, pathlib

MD = pathlib.Path(__file__).with_name("pathway-becoming.md")

PRINCIPLES = [
    "The self you practised yesterday is the one who runs today — until you see the loop and step out of it.",
    "You are not your body, your surroundings, or the hour. Become greater than the three and the known self has nothing left to hold onto.",
    "A future rehearsed in detail stops being strange. Walk it often enough and you will recognise it when it arrives.",
    "Gratitude is the state of having received. Feel it before the evidence and you stop waiting for your life to give you permission.",
    "When the heart and the breath run one rhythm, the signal is clean. A settled state carries further than a loud wish.",
    "The old feeling will come back. That is not failure — it is a habit asking to be fed. Notice it, and do not feed it.",
    "Doing follows being. Decide who you are, and the actions stop needing to be argued for.",
    "Hold the what and the who. Put down the how and the when. Gripping the method is how you keep the outcome at arm's length.",
    "The sitting is the rehearsal. The hour after it is the performance. Carry the state out and let it choose for you.",
]


def blockquote(chunk):
    out = []
    for ln in chunk.strip().split("\n"):
        ln = ln.strip()
        if ln.startswith(">"):
            ln = ln[1:].strip()
        if ln:
            out.append(ln)
    return " ".join(out)


def parse():
    txt = MD.read_text(encoding="utf-8")
    lessons = []
    for blk in re.split(r"\n## Lesson ", txt)[1:]:
        head, body = blk.split("\n", 1)
        num, title = head.split(" — ", 1)
        eyebrow = re.search(r"\*\*Eyebrow:\*\* `([^`]+)`", body).group(1)
        invitation = re.search(r"\*\*Invitation:\*\* `([^`]+)`", body).group(1)

        teach_raw = re.search(r"### Teaching\n(.*?)\n### The practice", body, re.S).group(1)
        teach = [" ".join(p.split()) for p in teach_raw.strip().split("\n\n") if p.strip()]

        practice_raw = re.search(r"### The practice\n(.*?)\n### Journal prompt", body, re.S).group(1)
        segs = []
        parts = re.split(r"> \*\*Segment \d+ — ", practice_raw)[1:]
        for part in parts:
            name = part.split("**", 1)[0].strip()
            cue = re.search(r"cue: `([^`]+)`", part).group(1)
            secs = int(re.search(r"· (\d+)s", part).group(1))
            after = part.split("\n", 1)[1]
            say = [l.strip().lstrip(">").strip()
                   for l in after.split("\n")
                   if l.strip().startswith(">") and l.strip(" >")]
            segs.append({"name": name, "cue": cue, "secs": secs, "say": say})

        prompt = blockquote(re.search(r"### Journal prompt\n(.*?)\n### What done looks like",
                                      body, re.S).group(1))
        done = " ".join(re.search(r"### What done looks like\n(.*?)(?:\n### |\n---)",
                                  body, re.S).group(1).split())

        lessons.append({
            "code": "becoming_%s" % num,
            "title": title.strip(),
            "eyebrow": eyebrow,
            "invitation": invitation,
            "teach": teach,
            "practice": segs,
            "prompt": prompt,
            "done": done,
            "principle": PRINCIPLES[len(lessons)],
            "steps": [prompt],
        })
    return lessons


if __name__ == "__main__":
    ls = parse()
    assert len(ls) == 9, len(ls)
    for l in ls:
        assert l["teach"] and l["practice"] and l["prompt"] and l["done"], l["code"]
        assert len(l["prompt"]) <= 300, (l["code"], len(l["prompt"]))
        for s in l["practice"]:
            assert s["say"], (l["code"], s["name"])
    body = pprint.pformat(ls, width=100, sort_dicts=False)
    out = ('BECOMING_ARC = ("Nine sittings. You rehearse the self you are becoming '
           'until it is the one who shows up.")\n\nBECOMING_PLAN = ' + body + "\n")
    pathlib.Path(__file__).with_name("becoming_plan.py").write_text(out, encoding="utf-8")
    print("lessons:", len(ls))
    for l in ls:
        print("  %s  teach=%d segs=%d say=%d prompt=%d" % (
            l["code"], len(l["teach"]), len(l["practice"]),
            sum(len(s["say"]) for s in l["practice"]), len(l["prompt"])))
