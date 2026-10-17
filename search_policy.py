
import pymupdf


def process_pdf(pdf_path):
    document = pymupdf.open(pdf_path)
    passages = []

    for page_index, page in enumerate(document):
        text = page.get_text("text")

        if not text.strip():
            continue

        passages.append({
            "text": text.strip(),
            "page": page_index + 1,
            "source": pdf_path
        })

    return passages



def keyword_search(question, passages):
    stop_words = {
        "a", "an", "the", "is", "are", "am",
        "do", "does", "did", "my", "me", "i",
        "you", "your", "we", "our", "it",
        "in", "on", "at", "to", "for", "of",
        "and", "or", "but", "when", "what",
        "how", "will", "would", "can", "could",
        "be", "been", "being", "have", "has",
        "had", "this", "that", "with", "while"
    }

    keywords = [
        word.strip(".,?!'\"()").lower()
        for word in question.split()
    ]

    keywords = [
        word for word in keywords
        if word and word not in stop_words
    ]

    results = []

    for passage in passages:
        text = passage["text"].lower()
        score = 0

        for word in keywords:
            score += text.count(word)

        if score > 0:
            results.append({
                **passage,
                "score": score
            })

    results.sort(
        key=lambda result: result["score"],
        reverse=True
    )

    return results



# Read the policy
policy = process_pdf("policies/sample_cigna.pdf")

# Ask a sample question
question = "Does my plan cover emergency surgery when travelling abroad?"

# Search the policy
results = keyword_search(question, policy)

# Display the results
print("Question:", question)
print("Matching passages:", len(results))

for result in results[:5]:
    print("\n------------------------------")
    print("Page:", result["page"])
    print("Match score:", result["score"])
    print("Text:")
    print(result["text"][:700])
