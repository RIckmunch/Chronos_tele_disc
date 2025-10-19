# Discord Bot - Chronos Pipeline Integration Instructions

**For Claude Code Agent:** Follow these instructions to integrate the existing Chronos pipeline with a Discord bot in ElizaOS.

---

## ⚠️ CRITICAL WARNINGS - Read First!

### **What NOT to Do:**

1. ❌ **DO NOT skip Neo4j** - It's ESSENTIAL for pattern discovery, not just storage
2. ❌ **DO NOT create a new pipeline implementation** - Use the existing `run_pipeline()` from `chronos/app/pipeline.py`
3. ❌ **DO NOT try to mimic the pipeline** - Call it via subprocess
4. ❌ **DO NOT read results from files** - Parse from stdout to avoid race conditions
5. ❌ **DO NOT hardcode credentials** - All values must come from `.env`
6. ❌ **DO NOT forget to clear Neo4j** - Each image needs isolated analysis

---

## 📋 Working Architecture Overview (Telegram - Reference)

```
User uploads image to Telegram
    ↓
ElizaOS plugin.ts (TELEGRAM_MESSAGE_RECEIVED event)
    ↓
Downloads image to temp_images/ folder
    ↓
Calls: python3 chronos/telegram_main.py <image_path> <user_id>
    ↓
telegram_main.py executes:
    1. Clear Neo4j database (isolated analysis)
    2. OCR extraction (Gemini API)
    3. Knowledge Graph building (OpenAI GPT-4o-mini → Neo4j)
    4. Pattern Discovery (Neo4j queries)
    5. Hypothesis Verification (FutureHouse API)
    6. Output structured results to stdout
    ↓
plugin.ts parses stdout between TELEGRAM_RESULTS_START/END markers
    ↓
Sends full hypothesis answers to Telegram (with smart message splitting)
```

---

## 🎯 Your Task: Discord Integration

You need to create the **exact same architecture** but for Discord instead of Telegram.

---

## 📁 Files You'll Work With

### **Files to CREATE:**
1. `/chronos/discord_main.py` - Discord-specific wrapper (copy and adapt from `telegram_main.py`)

### **Files to MODIFY:**
1. `/src/plugin.ts` - Add Discord event handler (similar to TELEGRAM_MESSAGE_RECEIVED)
2. `/.env` - Add Discord bot token (if not already present)

### **Files to REFERENCE (DO NOT MODIFY):**
- `/chronos/telegram_main.py` - Working reference implementation
- `/chronos/app/pipeline.py` - The actual Chronos pipeline
- `/chronos/app/neo4j_cleanup.py` - Neo4j database cleanup utility

---

## 🔧 Step-by-Step Implementation

### **Step 1: Create `discord_main.py`**

Create `/chronos/discord_main.py` by copying `/chronos/telegram_main.py` and making these changes:

```python
"""
Discord-specific wrapper for Chronos main.py
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


def process_discord_image(image_path: str, user_id: str = "discord_user"):
    """
    Process a single Discord image through the full Chronos pipeline.

    Args:
        image_path: Path to the downloaded image
        user_id: Discord user ID for tracking
    """

    # Configuration
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    element_id = f"discord_{user_id}_{timestamp}"

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
    print("🚀 CHRONOS PIPELINE - DISCORD IMAGE PROCESSING")
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

            # Output results in a parseable format for Discord bot
            print("\n" + "="*80)
            print("DISCORD_RESULTS_START")
            print("="*80)

            for i, result in enumerate(results, 1):
                print(f"QUESTION_{i}:::{result['question']}")
                print(f"ANSWER_{i}:::{result['owl_answer']}")
                print("---")

            print("="*80)
            print("DISCORD_RESULTS_END")
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
        print("Usage: python discord_main.py <image_path> [user_id]")
        sys.exit(1)

    image_path = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else "discord_user"

    if not os.path.exists(image_path):
        print(f"❌ Error: Image not found at {image_path}")
        sys.exit(1)

    process_discord_image(image_path, user_id)
```

**Changes from telegram_main.py:**
- Function name: `process_telegram_image` → `process_discord_image`
- Element ID prefix: `telegram_` → `discord_`
- Output markers: `TELEGRAM_RESULTS_START/END` → `DISCORD_RESULTS_START/END`
- Print banner: "TELEGRAM IMAGE PROCESSING" → "DISCORD IMAGE PROCESSING"

---

### **Issue: "No DISCORD_RESULTS block found"**

**Cause:** Python script crashed or didn't output results
**Fix:** Check terminal logs for Python errors. Common causes:
- Neo4j not running
- API keys missing or invalid
- FutureHouse API rate limit hit

### **Issue: Results are truncated**

**Cause:** Message exceeds Discord's 2000 character limit
**Fix:** Already handled by smart message splitting. If still truncated, reduce `DISCORD_MAX_LENGTH` further.

### **Issue: Same hypotheses for different images**

**Cause:** Neo4j not being cleared between images
**Fix:** Verify `clear_neo4j_database()` is being called successfully. Check Neo4j connection.

---

## 📊 Key Concepts

### **Why Clear Neo4j Before Each Image?**

Neo4j accumulates graphs from all previous images. Without clearing:
- Pattern discovery finds patterns across ALL historical images
- Same hypotheses returned regardless of new image content

Clearing ensures **isolated analysis** for each image.

### **Why Parse from stdout Instead of Files?**

Reading from files (`hypothesis_results/`) causes race conditions with multiple users:
- User A uploads image → processing starts → writes to `result_1.txt`
- User B uploads image → processing starts → writes to `result_2.txt`
- User A's bot might read `result_2.txt` by mistake

Parsing stdout ties results to the specific subprocess execution.

### **Why Use a Wrapper Script?**

The existing pipeline (`chronos/app/main.py`) is designed for:
- Interactive CLI usage
- PDF processing
- Direct file I/O

We need:
- Non-interactive execution
- Image processing
- Structured stdout output
- Platform-specific configuration (Discord vs Telegram)

The wrapper script (`discord_main.py`) adapts the pipeline for bot integration without modifying the core pipeline code.

---

## 📝 Summary

**What You're Creating:**
1. `discord_main.py` - Python wrapper that calls the Chronos pipeline and outputs structured results

**What You're NOT Doing:**
- Modifying the core Chronos pipeline
- Implementing your own OCR/KG/hypothesis logic
- Skipping any pipeline steps

**Key Success Factors:**
- Use the existing pipeline through subprocess
- Clear Neo4j for isolated analysis
- Parse results from stdout (not files)
- Handle Discord's 2000 character limit
- Load all credentials from `.env`

---