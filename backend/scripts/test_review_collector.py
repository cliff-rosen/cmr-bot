"""
Test script for the Review Collector Agent.

Run with: python -m scripts.test_review_collector
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.builtin.review_collector import execute_review_collector


class MockDB:
    pass


def test_collection(name: str, location: str, source: str):
    print(f"\n{'='*70}")
    print(f"COLLECTING: {source.upper()} reviews for {name} ({location})")
    print(f"{'='*70}")

    params = {"business_name": name, "location": location, "source": source}
    context = {}

    generator = execute_review_collector(params, MockDB(), 1, context)

    result = None
    try:
        while True:
            item = next(generator)
            if hasattr(item, 'stage'):
                print(f"[{item.stage}] {item.message}")
    except StopIteration as e:
        result = e.value

    if result:
        print(f"\n{'='*50}")
        print("RESULT:")
        print(f"{'='*50}")
        print(result.text)
        print(f"\n{'='*50}")
        print("DATA:")
        print(f"{'='*50}")
        import json
        print(json.dumps(result.data, indent=2, default=str))

    return result


def main():
    print("Review Collector Agent Test")
    print("="*70)
    print("Testing single-source collection with entity verification")
    print("="*70)

    # Test 1: Yelp with a specific, identifiable business
    test_collection("Cambridge Endodontics", "Cambridge, MA", "yelp")

    # Uncomment to test other sources:
    # test_collection("Cambridge Endodontics", "Cambridge, MA", "google")
    # test_collection("Cambridge Endodontics", "Cambridge, MA", "reddit")

    # Test with an ambiguous name to verify entity resolution failure
    # test_collection("Eye Care Center", "Boulder, CO", "yelp")


if __name__ == "__main__":
    main()
