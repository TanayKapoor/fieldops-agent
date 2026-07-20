"""Smoke test for knowledge_service. Run: python -m backend.services.test_knowledge_service"""

from backend.services import knowledge_service as ks


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"failed: {label}")


def main():
    check("parsed 5 sections", len(ks._SECTIONS) == 5)

    section, score = ks.search("how do I reset a CU cooling unit")
    check("reset query matches section 1", section is not None and section.title.startswith("1."))
    check("reset query clears threshold", score >= ks.MIN_SCORE_THRESHOLD)

    section, score = ks.search("lockout tagout safety procedure before servicing")
    check("lockout query matches section 2", section is not None and section.title.startswith("2."))

    section, score = ks.search("warranty labor coverage period")
    check("warranty query matches section 3", section is not None and section.title.startswith("3."))

    section, score = ks.search("when should I escalate to a supervisor")
    check("escalate query matches section 4", section is not None and section.title.startswith("4."))

    section, score = ks.search("replace air filter AF series")
    check("filter query matches section 5", section is not None and section.title.startswith("5."))

    section, score = ks.search("what is the capital of France")
    check("unrelated query returns no match", section is None)
    check("unrelated query score below threshold", score < ks.MIN_SCORE_THRESHOLD)

    print("ok")


if __name__ == "__main__":
    main()
