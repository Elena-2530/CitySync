
from services.social_filter import analyze_social_text


test_posts = [
    "Traffico intenso a Fuorigrotta, auto ferme da diversi minuti.",
    "Segnalato un allagamento in via Toledo dopo il temporale.",
    "Incendio a Bagnoli, si vede del fumo nella zona.",
    "La metro di Napoli è in ritardo questa mattina.",
    "Buona serata a tutti, oggi sono stata a Napoli!"
]


for i, post in enumerate(test_posts, start=1):
    result = analyze_social_text(post)

    print("\n" + "=" * 60)
    print(f"TEST {i}")
    print(f"POST: {post}")
    print(f"RILEVANTE: {result['relevant']}")
    print(f"CATEGORIE: {result['categories']}")
    print(f"LOCALITÀ: {result['locations']}")
    print(f"MOTIVAZIONE: {result['reason']}")
