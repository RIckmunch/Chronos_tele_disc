"""
Main Pipeline: OCR + Knowledge Graph for Historical Medical Documents
Connects OCR engine with knowledge graph extraction and Neo4j storage
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.loaders import UnstructuredIO
from camel.storages import Neo4jGraph
from KGAgents import KnowledgeGraphAgent
from ocr_engine import OCREngine
from typing import Optional, Dict, Any, Tuple

# Load environment from parent .env file (telegram-bot/.env)
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class KnowledgeGraphPipeline:
    """
    Pipeline for extracting knowledge graphs from medical documents.
    """
    
    def __init__(
        self,
        neo4j_url: str = "neo4j://127.0.0.1:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "0123456789",
        use_advanced_kg_model: bool = False
    ):
        """
        Initialize Knowledge Graph pipeline.
        
        Args:
            neo4j_url: Neo4j database URL
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
            use_advanced_kg_model: Use GPT-4 for KG extraction (more expensive but better)
        """
        self.n4j_graph = self._configure_neo4j(neo4j_url, neo4j_username, neo4j_password)
        self.kg_model = self._configure_kg_model(use_advanced_kg_model)
        print("✅ Knowledge Graph pipeline initialized")
    
    def _configure_neo4j(self, url: str, username: str, password: str) -> Neo4jGraph:
        """Configure Neo4j database connection."""
        print("🔌 Connecting to Neo4j database...")
        n4j = Neo4jGraph(url=url, username=username, password=password)
        print("✅ Neo4j connection established!")
        return n4j
    
    def _configure_kg_model(self, use_advanced: bool):
        """Configure LLM model for Knowledge Graph extraction."""
        print("🤖 Setting up Knowledge Graph model...")
        
        model_type = ModelType.GPT_4O if use_advanced else ModelType.GPT_4O_MINI
        
        llama = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=model_type,
            api_key=os.environ.get("OPENAI_API_KEY"),
            model_config_dict={
                "temperature": 0.2,
                "max_tokens": 10000
            }
        )
        print(f"✅ KG model configured: {model_type}")
        return llama
    
    def _chunk_text(self, text: str, max_chars: int = 15000, overlap: int = 500) -> list:
        """
        Split large text into overlapping chunks.
        
        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk
            overlap: Overlap between chunks to maintain context
        
        Returns:
            List of text chunks
        """
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_chars
            
            # Try to break at paragraph or sentence boundary
            if end < len(text):
                # Look for paragraph break
                paragraph_break = text.rfind('\n\n', start, end)
                if paragraph_break > start + max_chars // 2:
                    end = paragraph_break
                else:
                    # Look for sentence break
                    sentence_break = text.rfind('. ', start, end)
                    if sentence_break > start + max_chars // 2:
                        end = sentence_break + 1
            
            chunks.append(text[start:end])
            start = end - overlap if end < len(text) else end
        
        return chunks
    
    def extract_and_store_knowledge_graph(
        self,
        text: str,
        element_id: str = "0",
        chunk_size: int = 15000,
        use_chunking: bool = True
    ) -> list:
        """
        Extract knowledge graph from text and store in Neo4j.
        Automatically chunks large documents to avoid token limits.
        
        Args:
            text: Extracted text from OCR
            element_id: Unique identifier for this document
            chunk_size: Maximum characters per chunk (default: 15000)
            use_chunking: Enable automatic chunking for large documents
        
        Returns:
            List of graph elements (one per chunk)
        """
        print("\n🧠 Extracting knowledge graph from text...")
        
        # Determine if chunking is needed
        needs_chunking = use_chunking and len(text) > chunk_size
        
        if needs_chunking:
            print(f"  📊 Large document detected ({len(text):,} chars)")
            chunks = self._chunk_text(text, max_chars=chunk_size)
            print(f"  ✂️  Split into {len(chunks)} chunks for processing")
        else:
            chunks = [text]
            if len(text) > 50000:
                print(f"  ⚠️  Warning: Large document ({len(text):,} chars) without chunking may hit token limits")
        
        uio = UnstructuredIO()
        kg_agent = KnowledgeGraphAgent(model=self.kg_model)
        
        all_graph_elements = []
        
        for i, chunk in enumerate(chunks, 1):
            chunk_id = f"{element_id}_chunk_{i}" if len(chunks) > 1 else element_id
            
            if len(chunks) > 1:
                print(f"\n  📝 Processing chunk {i}/{len(chunks)} ({len(chunk):,} chars)")
            else:
                print(f"  📝 Creating text element...")
            
            try:
                element = uio.create_element_from_text(text=chunk, element_id=chunk_id)
                
                print(f"  🔍 Extracting graph elements...")
                graph_elements = kg_agent.run(element, parse_graph_elements=True)
                
                print(f"  💾 Storing in Neo4j database...")
                self.n4j_graph.add_graph_elements(graph_elements=[graph_elements])
                
                all_graph_elements.append(graph_elements)
                
                if len(chunks) > 1:
                    print(f"  ✅ Chunk {i}/{len(chunks)} completed")
                
            except Exception as e:
                print(f"  ❌ Error processing chunk {i}: {e}")
                if len(chunks) > 1:
                    print(f"  ⏭️  Continuing with next chunk...")
                    continue
                else:
                    raise
        
        print(f"\n✅ Knowledge graph stored successfully! ({len(all_graph_elements)} chunks processed)")
        
        return all_graph_elements


class MedicalDocumentPipeline:
    """
    Complete pipeline: OCR -> Text Extraction -> Knowledge Graph -> Neo4j Storage
    """
    
    def __init__(
        self,
        google_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        neo4j_url: str = "neo4j://127.0.0.1:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "0123456789",
        use_advanced_ocr: bool = True,
        use_advanced_kg: bool = False
    ):
        """
        Initialize the complete medical document processing pipeline.
        
        Args:
            google_api_key: Google API key for OCR (optional, reads from env)
            openai_api_key: OpenAI API key for KG (optional, reads from env)
            neo4j_url: Neo4j database URL
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
            use_advanced_ocr: Use advanced Gemini model
            use_advanced_kg: Use GPT-4 for knowledge graph
        """
        print("=" * 80)
        print("🚀 MEDICAL DOCUMENT PROCESSING PIPELINE")
        print("=" * 80)
        
        # Initialize OCR engine
        self.ocr_engine = OCREngine(api_key=google_api_key, use_advanced_model=use_advanced_ocr)
        
        # Initialize Knowledge Graph pipeline
        self.kg_pipeline = KnowledgeGraphPipeline(
            neo4j_url=neo4j_url,
            neo4j_username=neo4j_username,
            neo4j_password=neo4j_password,
            use_advanced_kg_model=use_advanced_kg
        )
        
        print("✅ Pipeline fully initialized and ready!")
    
    def process_document(
        self,
        input_file: str,
        output_text_file: Optional[str] = None,
        ocr_config: Optional[Dict[str, Any]] = None,
        element_id: str = "0",
        kg_chunk_size: int = 15000,
        enable_chunking: bool = True
    ) -> Tuple[str, Any]:
        """
        Process a medical document through the complete pipeline.
        
        Args:
            input_file: Path to PDF or image file
            output_text_file: Optional path to save extracted text
            ocr_config: Dictionary of OCR configuration options:
                - use_preprocessing: bool (default: True)
                - enhancement_level: str (default: "medium")
                - use_high_dpi: bool (default: True)
                - medical_context: bool (default: True)
                - save_debug_images: bool (default: False)
                - try_native_text: bool (default: True)
            element_id: Unique identifier for this document in the knowledge graph
            kg_chunk_size: Maximum characters per KG chunk (default: 15000)
            enable_chunking: Automatically chunk large documents (default: True)
        
        Returns:
            Tuple of (extracted_text, graph_elements)
        """
        # Default OCR configuration
        default_config = {
            "use_preprocessing": True,
            "enhancement_level": "medium",
            "high_dpi": True,
            "medical_context": True,
            "save_debug_images": False,
            "try_native_text": True
        }
        
        # Merge with user config
        if ocr_config:
            default_config.update(ocr_config)
        
        print("\n" + "="*80)
        print("📋 CONFIGURATION")
        print("="*80)
        print(f"Input: {input_file}")
        for key, value in default_config.items():
            print(f"   - {key}: {value}")
        print(f"   - kg_chunk_size: {kg_chunk_size}")
        print(f"   - enable_chunking: {enable_chunking}")
        
        # Step 1: Extract text using OCR
        print("\n" + "="*80)
        print("📋 STEP 1: Extract Text from Document")
        print("="*80)
        extracted_text = self.ocr_engine.process_file(input_file, **default_config)
        
        # Save extracted text if requested
        if output_text_file:
            print(f"\n💾 Saving extracted text to: {output_text_file}")
            with open(output_text_file, "w", encoding="utf-8") as f:
                f.write(extracted_text)
            print("✅ Text saved successfully!")
        
        # Step 2: Extract and store knowledge graph
        print("\n" + "="*80)
        print("📋 STEP 2: Build and Store Knowledge Graph")
        print("="*80)
        graph_elements = self.kg_pipeline.extract_and_store_knowledge_graph(
            extracted_text,
            element_id=element_id,
            chunk_size=kg_chunk_size,
            use_chunking=enable_chunking
        )
        
        # Summary
        print("\n" + "=" * 80)
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print(f"\n📊 Summary:")
        print(f"   - Extracted text length: {len(extracted_text):,} characters")
        print(f"   - Output saved to: {output_text_file if output_text_file else 'Not saved'}")
        print(f"   - Knowledge graph chunks: {len(graph_elements) if isinstance(graph_elements, list) else 1}")
        print(f"   - Knowledge graph stored in Neo4j")
        
        return extracted_text, graph_elements


def run_pipeline(
    input_file: str,
    output_text_file: Optional[str] = None,
    neo4j_url: str = "neo4j://127.0.0.1:7687",
    neo4j_username: str = "neo4j",
    neo4j_password: str = "0123456789",
    ocr_preprocessing: bool = True,
    enhancement_level: str = "medium",
    use_high_dpi: bool = True,
    use_advanced_ocr: bool = True,
    use_advanced_kg: bool = False,
    medical_context: bool = True,
    save_debug_images: bool = False,
    try_native_text: bool = True,
    element_id: str = "0",
    kg_chunk_size: int = 15000,
    enable_chunking: bool = True
) -> Tuple[str, Any]:
    """
    Convenience function to run the complete pipeline with individual parameters.
    
    Args:
        input_file: Path to PDF or image file
        output_text_file: Optional path to save extracted text
        neo4j_url: Neo4j database URL
        neo4j_username: Neo4j username
        neo4j_password: Neo4j password
        ocr_preprocessing: Apply image enhancement
        enhancement_level: "light", "medium", or "aggressive"
        use_high_dpi: Use 300 DPI for PDF rendering
        use_advanced_ocr: Use gemini-2.0-flash-exp model
        use_advanced_kg: Use GPT-4 for knowledge graph
        medical_context: Use medical-specific prompting
        save_debug_images: Save preprocessed images to debug_images/
        try_native_text: Try extracting native PDF text before OCR
        element_id: Unique identifier for this document
        kg_chunk_size: Maximum characters per KG chunk (default: 15000)
        enable_chunking: Automatically chunk large documents (default: True)
    
    Returns:
        Tuple of (extracted_text, graph_elements)
    """
    # Initialize pipeline
    pipeline = MedicalDocumentPipeline(
        neo4j_url=neo4j_url,
        neo4j_username=neo4j_username,
        neo4j_password=neo4j_password,
        use_advanced_ocr=use_advanced_ocr,
        use_advanced_kg=use_advanced_kg
    )
    
    # Configure OCR settings
    ocr_config = {
        "use_preprocessing": ocr_preprocessing,
        "enhancement_level": enhancement_level,
        "high_dpi": use_high_dpi,
        "medical_context": medical_context,
        "save_debug_images": save_debug_images,
        "try_native_text": try_native_text
    }
    
    # Run pipeline
    return pipeline.process_document(
        input_file=input_file,
        output_text_file=output_text_file,
        ocr_config=ocr_config,
        element_id=element_id,
        kg_chunk_size=kg_chunk_size,
        enable_chunking=enable_chunking
    )


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    # Configuration
    INPUT_FILE = "/home/sidharth/Downloads/Staffel_1889_Die_menschlichen_Haltungstypen_und_ihre_Beziehungen_removed.pdf"
    OUTPUT_TEXT_FILE = "/home/sidharth/Desktop/ocr_output_enhanced.txt"
    
    # Neo4j Configuration
    NEO4J_URL = "neo4j://127.0.0.1:7687"
    NEO4J_USERNAME = "neo4j"
    NEO4J_PASSWORD = "0123456789"
    
    # OCR Settings for old medical documents
    OCR_CONFIG = {
        "ocr_preprocessing": True,
        "enhancement_level": "aggressive",
        "use_high_dpi": True,
        "use_advanced_ocr": True,
        "use_advanced_kg": False,
        "medical_context": True,
        "save_debug_images": True,
        "try_native_text": True
    }
    
    # Run pipeline
    try:
        extracted_text, graph_elements = run_pipeline(
            input_file=INPUT_FILE,
            output_text_file=OUTPUT_TEXT_FILE,
            neo4j_url=NEO4J_URL,
            neo4j_username=NEO4J_USERNAME,
            neo4j_password=NEO4J_PASSWORD,
            **OCR_CONFIG
        )
        
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()