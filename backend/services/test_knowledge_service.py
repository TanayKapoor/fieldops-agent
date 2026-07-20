"""Smoke test for knowledge_service. Run: python -m backend.services.test_knowledge_service"""

from backend.services import knowledge_service as ks


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"failed: {label}")


def main():
    check("parsed 5 sections", len(ks._SECTIONS) == 5)

    section, score = ks.search("How do I reset a CU unit?")
    check("reset query matches section 1", section is not None and section.heading.startswith("1."))
    check("reset query clears threshold", score >= ks.MIN_SCORE_THRESHOLD)

    section, score = ks.search("What's the warranty period on parts?")
    check("warranty query matches section 3", section is not None and section.heading.startswith("3."))

    section, score = ks.search("What's the weather today?")
    check("weather query returns no match", section is None)
    check("weather query score below threshold", score < ks.MIN_SCORE_THRESHOLD)

    section, score = ks.search("Can I remove someone else's lockout tag?")
    check("lockout tag query matches section 2", section is not None and section.heading.startswith("2."))

    section, score = ks.search("When should I escalate a work order?")
    check("escalate query matches section 4", section is not None and section.heading.startswith("4."))

    section, score = ks.search("How often should I replace the air filter?")
    check("filter query matches section 5", section is not None and section.heading.startswith("5."))

    print("ok")


if __name__ == "__main__":
    main()
