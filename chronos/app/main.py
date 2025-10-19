"""
Main Script - Fixed Version with Automatic Chunking
Run this to process your medical documents with proper knowledge graph creation
"""

from pathlib import Path
from dotenv import load_dotenv
from pipeline import run_pipeline
from neo4j_utils import verify_knowledge_graph
from kg_pattern_discovery import KGPatternDiscovery
from hypothesis_verifier import HypothesisVerifier
import os

# Load environment from parent .env file (telegram-bot/.env)
load_dotenv(Path(__file__).parent.parent.parent / ".env")


def main():
    """
    Main execution with proper settings for large documents.
    """
    
    # ==================== CONFIGURATION ====================
    
    # Input/Output Files
    INPUT_FILE = "/home/sidharth/Desktop/HeritageNet-example/Staffel_1889_Die_menschlichen_Haltungstypen_und_ihre_Beziehungen_removed.pdf"
    OUTPUT_TEXT_FILE = "/home/sidharth/Desktop/HeritageNet-example/out.txt"
    
    # Neo4j Configuration from environment
    NEO4J_URL = os.environ.get("NEO4J_URL", "neo4j://127.0.0.1:7687")
    NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "0123456789")
    
    # OCR Settings for old medical documents
    OCR_CONFIG = {
        "ocr_preprocessing": True,
        "enhancement_level": "aggressive",  # For very old documents
        "use_high_dpi": True,
        "use_advanced_ocr": True,
        "medical_context": True,
        "save_debug_images": True,
        "try_native_text": True
    }
    
    # Knowledge Graph Settings - CRITICAL FOR LARGE DOCUMENTS
    KG_CONFIG = {
        "use_advanced_kg": False,      # Use GPT-4o-mini (cost effective)
        "kg_chunk_size": 10000,        # 15k chars per chunk (adjust if needed)
        "enable_chunking": True,       # AUTO-CHUNK LARGE DOCUMENTS
        "element_id": "staffel_1889"   # Unique ID for this document
    }
    
    # ==================== EXECUTION ====================
    
    print("\n" + "="*80)
    print("🚀 MEDICAL DOCUMENT PROCESSING PIPELINE (FIXED VERSION)")
    print("="*80)
    
    # Check if file exists
    if not os.path.exists(INPUT_FILE):
        print(f"\n❌ ERROR: Input file not found: {INPUT_FILE}")
        print("   Please update INPUT_FILE path in the script")
        return
    
    print(f"\n📄 Input: {INPUT_FILE}")
    print(f"📝 Output: {OUTPUT_TEXT_FILE}")
    print(f"💾 Neo4j: {NEO4J_URL}")
    print(f"\n⚙️  Settings:")
    print(f"   - OCR Enhancement: {OCR_CONFIG['enhancement_level']}")
    print(f"   - Medical Context: {OCR_CONFIG['medical_context']}")
    print(f"   - KG Chunking: {KG_CONFIG['enable_chunking']}")
    print(f"   - Chunk Size: {KG_CONFIG['kg_chunk_size']:,} characters")
    
    # Confirm before proceeding
    print("\n" + "="*80)
    response = input("Proceed with processing? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    # Run pipeline
    try:
        print("\n" + "="*80)
        print("STARTING PIPELINE")
        print("="*80)
        
        extracted_text, graph_elements = run_pipeline(
            input_file=INPUT_FILE,
            output_text_file=OUTPUT_TEXT_FILE,
            neo4j_url=NEO4J_URL,
            neo4j_username=NEO4J_USERNAME,
            neo4j_password=NEO4J_PASSWORD,
            **OCR_CONFIG,
            **KG_CONFIG
        )
        
        # Verify results
        print("\n" + "="*80)
        print("VERIFICATION")
        print("="*80)
        
        print(f"\n✅ Text extraction complete:")
        print(f"   - Characters extracted: {len(extracted_text):,}")
        print(f"   - Saved to: {OUTPUT_TEXT_FILE}")
        
        print(f"\n🔍 Verifying Knowledge Graph...")
        success = verify_knowledge_graph(
            uri=NEO4J_URL,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            show_samples=True
        )
        
        if success:
            print("\n✅ PIPELINE COMPLETED SUCCESSFULLY!")
            
            # ==================== PATTERN DISCOVERY & HYPOTHESIS VERIFICATION ====================
            print("\n" + "="*80)
            print("🔍 STARTING PATTERN DISCOVERY & HYPOTHESIS VERIFICATION")
            print("="*80)
            
            try:
                # Step 1: Discover patterns and generate questions
                print("\n📊 Step 1: Discovering patterns in knowledge graph...")
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
                else:
                    print(f"\n✅ Generated {len(questions)} questions from patterns")
                    
                    # Step 2: Verify hypotheses
                    print("\n🔬 Step 2: Verifying hypotheses with FutureHouse API...")
                    verifier = HypothesisVerifier(output_dir="hypothesis_results")
                    
                    # Process only first 2 questions
                    results = verifier.verify_questions_sync(questions)
                    
                    print("\n" + "="*80)
                    print("✅ HYPOTHESIS VERIFICATION COMPLETE")
                    print("="*80)
                    print(f"Total questions verified: {len(results)}")
                    print(f"Results saved in: hypothesis_results/")
                    
            except Exception as e:
                print(f"\n⚠️  Pattern discovery/verification failed: {e}")
                import traceback
                traceback.print_exc()
                print("\nContinuing without hypothesis verification...")
            
            print("\n💡 Next steps:")
            print("   1. Open Neo4j Browser: http://localhost:7474")
            print("   2. Run queries to explore the knowledge graph")
            print("   3. View extracted text in:", OUTPUT_TEXT_FILE)
            print("   4. Check hypothesis results in: hypothesis_results/")
        else:
            print("\n⚠️  WARNING: Knowledge graph appears empty!")
            print("   Check the output above for errors")
            print("   You may need to:")
            print("   - Reduce kg_chunk_size (try 10000)")
            print("   - Check Neo4j connection")
            print("   - Review OpenAI API key and quota")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n\n❌ PIPELINE FAILED")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n💡 Troubleshooting:")
        print("   1. Check all API keys in .env file")
        print("   2. Verify Neo4j is running")
        print("   3. Check input file path")
        print("   4. Review error message above")


def quick_verify():
    """Quick verification without processing."""
    print("\n" + "="*80)
    print("🔍 QUICK VERIFICATION")
    print("="*80)

    verify_knowledge_graph(
        uri=os.environ.get("NEO4J_URL", "neo4j://127.0.0.1:7687"),
        username=os.environ.get("NEO4J_USERNAME", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "0123456789"),
        show_samples=True
    )


def process_multiple_documents():
    """Example: Process multiple documents in batch."""
    from pipeline import MedicalDocumentPipeline
    
    # Document list
    documents = [
        ("doc1.pdf", "output1.txt", "doc_001"),
        ("doc2.pdf", "output2.txt", "doc_002"),
        ("doc3.pdf", "output3.txt", "doc_003"),
    ]
    
    # Initialize pipeline once
    pipeline = MedicalDocumentPipeline(
        neo4j_url=os.environ.get("NEO4J_URL", "neo4j://127.0.0.1:7687"),
        neo4j_username=os.environ.get("NEO4J_USERNAME", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", "0123456789"),
        use_advanced_ocr=True,
        use_advanced_kg=False
    )
    
    # Process each document
    results = []
    for pdf_file, output_file, doc_id in documents:
        print(f"\n{'='*80}")
        print(f"Processing: {pdf_file}")
        
        try:
            if not os.path.exists(pdf_file):
                print(f"⚠️  File not found, skipping...")
                results.append((doc_id, "Skipped", 0))
                continue
            
            text, graph = pipeline.process_document(
                input_file=pdf_file,
                output_text_file=output_file,
                ocr_config={
                    "use_preprocessing": True,
                    "enhancement_level": "medium",
                    "medical_context": True,
                },
                element_id=doc_id,
                kg_chunk_size=15000,
                enable_chunking=True
            )
            
            results.append((doc_id, "Success", len(text)))
            print(f"✅ {doc_id} completed successfully")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append((doc_id, "Failed", 0))
    
    # Summary
    print("\n" + "="*80)
    print("BATCH PROCESSING SUMMARY")
    print("="*80)
    for doc_id, status, chars in results:
        print(f"   {doc_id}: {status} - {chars:,} characters")
    
    # Final verification
    print("\n")
    verify_knowledge_graph()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "verify":
            quick_verify()
        elif command == "batch":
            process_multiple_documents()
        else:
            print(f"Unknown command: {command}")
            print("Usage:")
            print("  python main.py         - Process single document")
            print("  python main.py verify  - Verify existing KG")
            print("  python main.py batch   - Process multiple documents")
    else:
        main()