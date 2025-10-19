"""
Telegram-specific wrapper for Chronos main.py
Processes a single image and returns hypothesis results
"""

import sys
import os
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from pipeline import run_pipeline
from neo4j_utils import verify_knowledge_graph
from kg_pattern_discovery import KGPatternDiscovery
from hypothesis_verifier import HypothesisVerifier
from neo4j_cleanup import clear_neo4j_database
from datetime import datetime


def process_telegram_image(image_path: str, user_id: str = "telegram_user"):
    """
    Process a single Telegram image through the full Chronos pipeline.

    Args:
        image_path: Path to the downloaded image
        user_id: Telegram user ID for tracking
    """

    # Configuration
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    element_id = f"telegram_{user_id}_{timestamp}"

    chronos_dir = Path(__file__).parent
    output_text_file = chronos_dir / "chronos_output" / f"{element_id}_text.txt"
    output_text_file.parent.mkdir(exist_ok=True)

    # Neo4j Configuration from environment
    from dotenv import load_dotenv
    load_dotenv(chronos_dir.parent / ".env")

    NEO4J_URL = os.environ.get("NEO4J_URL", "neo4j://127.0.0.1:7687")
    NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "0123456789")

    # OCR Settings for images
    OCR_CONFIG = {
        "ocr_preprocessing": True,
        "enhancement_level": "aggressive",
        "use_high_dpi": False,  # Not used for images, only PDFs
        "use_advanced_ocr": True,
        "medical_context": True,
        "save_debug_images": False,
        "try_native_text": False,  # Images don't have native text
    }

    # KG Config
    KG_CONFIG = {
        "use_advanced_kg": False,  # Use GPT-4o-mini (cost effective)
        "kg_chunk_size": 10000,
        "enable_chunking": True,
        "element_id": element_id
    }

    print("\n" + "="*80)
    print("🚀 CHRONOS PIPELINE - TELEGRAM IMAGE PROCESSING")
    print("="*80)
    print(f"📷 Image: {Path(image_path).name}")
    print(f"👤 User: {user_id}")
    print(f"🆔 Element: {element_id}")
    print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
    print("="*80)

    try:
        # STEP 0: Clear Neo4j database for isolated analysis
        print("\n" + "="*80)
        print("🧹 CLEARING NEO4J DATABASE")
        print("="*80)
        print(f"Clearing previous data to ensure isolated analysis for user {user_id}...")

        clear_success = clear_neo4j_database(
            neo4j_url=NEO4J_URL,
            neo4j_username=NEO4J_USERNAME,
            neo4j_password=NEO4J_PASSWORD
        )

        if not clear_success:
            print("⚠️  Warning: Neo4j cleanup may have failed, continuing anyway...")

        # Run pipeline
        print("\n" + "="*80)
        print("STARTING PIPELINE")
        print("="*80)

        extracted_text, graph_elements = run_pipeline(
            input_file=image_path,
            output_text_file=str(output_text_file),
            neo4j_url=NEO4J_URL,
            neo4j_username=NEO4J_USERNAME,
            neo4j_password=NEO4J_PASSWORD,
            **OCR_CONFIG,
            **KG_CONFIG
        )

        print(f"\n✅ Pipeline complete - {len(extracted_text):,} characters extracted")

        # Pattern Discovery & Hypothesis Verification
        print("\n" + "="*80)
        print("🔍 PATTERN DISCOVERY & HYPOTHESIS VERIFICATION")
        print("="*80)

        try:
            # Discover patterns
            print("\n📊 Discovering patterns in knowledge graph...")
            pattern_discovery = KGPatternDiscovery(
                neo4j_url=NEO4J_URL,
                neo4j_username=NEO4J_USERNAME,
                neo4j_password=NEO4J_PASSWORD
            )

            patterns = pattern_discovery.discover_patterns(
                max_length=3,
                max_patterns_per_length=5
            )
            pattern_discovery.close()

            # Extract questions
            questions = [p['question'] for p in patterns if p.get('question')]

            if not questions:
                print("\n⚠️  No questions generated from patterns")
                return

            print(f"\n✅ Generated {len(questions)} questions")

            # Verify hypotheses
            print("\n🔬 Verifying hypotheses with FutureHouse API...")
            verifier = HypothesisVerifier(output_dir=str(chronos_dir / "hypothesis_results"))
            results = verifier.verify_questions_sync(questions)

            print("\n" + "="*80)
            print("✅ PROCESSING COMPLETE")
            print("="*80)
            print(f"Total questions verified: {len(results)}")
            print(f"Results saved in: hypothesis_results/")

            # Output results in a parseable format for Telegram bot
            print("\n" + "="*80)
            print("TELEGRAM_RESULTS_START")
            print("="*80)

            for i, result in enumerate(results, 1):
                print(f"QUESTION_{i}:::{result['question']}")
                print(f"ANSWER_{i}:::{result['owl_answer']}")
                print("---")

            print("="*80)
            print("TELEGRAM_RESULTS_END")
            print("="*80)

        except Exception as e:
            print(f"\n⚠️  Pattern discovery/verification failed: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"\n\n❌ PIPELINE FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python telegram_main.py <image_path> [user_id]")
        sys.exit(1)

    image_path = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else "telegram_user"

    if not os.path.exists(image_path):
        print(f"❌ Error: Image not found at {image_path}")
        sys.exit(1)

    process_telegram_image(image_path, user_id)
