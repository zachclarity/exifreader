import base64, json, os, time, urllib.request, urllib.error

LAMBDA_URL = os.environ.get("LAMBDA_URL", "http://localstack:4566/lambda-url/ocr-lambda/").rstrip("/") + "/"
GT_PATH = os.path.join(os.path.dirname(__file__), "ground_truth.json")

def levenshtein(a, b):
    # classic DP, O(n*m)
    n, m = len(a), len(b)
    if n == 0: return m
    if m == 0: return n
    prev = list(range(m+1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0]*m
        for j, cb in enumerate(b, 1):
            ins = cur[j-1] + 1
            dele = prev[j] + 1
            sub = prev[j-1] + (ca != cb)
            cur[j] = min(ins, dele, sub)
        prev = cur
    return prev[m]

def cer(ref, hyp):
    ref = ref.strip()
    hyp = hyp.strip()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / max(1, len(ref))

def wer(ref, hyp):
    r = ref.strip().split()
    h = hyp.strip().split()
    if not r:
        return 0.0 if not h else 1.0
    # DP on words
    n, m = len(r), len(h)
    prev = list(range(m+1))
    for i in range(1, n+1):
        cur = [i] + [0]*m
        for j in range(1, m+1):
            ins = cur[j-1] + 1
            dele = prev[j] + 1
            sub = prev[j-1] + (r[i-1] != h[j-1])
            cur[j] = min(ins, dele, sub)
        prev = cur
    return prev[m] / max(1, n)

def call_lambda(image_path, filename):
    with open(image_path, "rb") as f:
        b = f.read()
    payload = json.dumps({
        "filename": filename,
        "contentType": "image/png",
        "imageBase64": base64.b64encode(b).decode("ascii"),
        "storeToS3": True
    }).encode("utf-8")

    req = urllib.request.Request(LAMBDA_URL, data=payload, headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    t1 = time.time()
    out = json.loads(body.decode("utf-8"))
    out["_clientElapsedMs"] = int((t1 - t0)*1000)
    return out

def main():
    with open(GT_PATH, "r", encoding="utf-8") as f:
        gt = json.load(f)

    results = []
    print(f"Benchmarking Lambda URL: {LAMBDA_URL}")
    for item in gt["cases"]:
        path = os.path.join(os.path.dirname(__file__), "test-images", item["file"])
        out = call_lambda(path, item["file"])
        hyp = (out.get("text") or "").strip()
        ref = item["text"].strip()
        results.append({
            "file": item["file"],
            "realOcr": out.get("realOcr"),
            "processingTimeMs": out.get("processingTimeMs"),
            "clientElapsedMs": out.get("_clientElapsedMs"),
            "cer": cer(ref, hyp),
            "wer": wer(ref, hyp),
        })
        print(f"- {item['file']}: realOcr={out.get('realOcr')} proc={out.get('processingTimeMs')}ms CER={results[-1]['cer']:.3f} WER={results[-1]['wer']:.3f}")

    avg_cer = sum(r["cer"] for r in results)/len(results)
    avg_wer = sum(r["wer"] for r in results)/len(results)
    avg_proc = sum((r["processingTimeMs"] or 0) for r in results)/len(results)

    print("\nSummary")
    print(f"Cases: {len(results)}")
    print(f"Avg processingTimeMs: {avg_proc:.1f}")
    print(f"Avg CER: {avg_cer:.3f}")
    print(f"Avg WER: {avg_wer:.3f}")

if __name__ == "__main__":
    main()
