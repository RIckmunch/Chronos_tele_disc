"""
Hypothesis Verification Module
Verifies questions using FutureHouse API and saves results
"""

import asyncio
from futurehouse_client import FutureHouseClient, JobNames
from dotenv import load_dotenv
from pathlib import Path
import os
from datetime import datetime

# Load environment from parent .env file (telegram-bot/.env)
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class HypothesisVerifier:
    """Verifies hypotheses using FutureHouse API."""
    
    def __init__(self, api_key=None, output_dir="hypothesis_results"):
        """
        Initialize hypothesis verifier.
        
        Args:
            api_key: FutureHouse API key (defaults to env variable)
            output_dir: Directory to save results
        """
        # Support both FUTUREHOUSE_API_KEY and FUTURE_HOUSE_API_KEY
        self.api_key = api_key or os.environ.get("FUTUREHOUSE_API_KEY") or os.environ.get("FUTURE_HOUSE_API_KEY")
        if not self.api_key:
            raise ValueError("FutureHouse API key not found. Set FUTUREHOUSE_API_KEY or FUTURE_HOUSE_API_KEY in .env")
        
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    async def verify_batch(self, questions, batch_size=2, wait_time=0):
        """
        Verify questions using FutureHouse API.
        Only processes first 2 questions and stops.
        
        Args:
            questions: List of question strings
            batch_size: Number of questions to process (default: 2)
            wait_time: Not used, kept for compatibility
            
        Returns:
            List of results with question, answer, and file path
        """
        # Only take first 2 questions
        questions_to_process = questions[:2]
        
        print(f"\n{'='*80}")
        print(f"🔬 Processing {len(questions_to_process)} questions (first 2 only)")
        print(f"{'='*80}")
        
        client = FutureHouseClient(api_key=self.api_key)
        
        # Prepare tasks - one OWL job per question
        task_data = []
        for question in questions_to_process:
            task_data.append({
                "name": JobNames.OWL,
                "query": question,
            })
        
        print(f"\n📤 Sending {len(task_data)} OWL requests to FutureHouse API")
        
        # Run tasks
        start_time = datetime.now()
        print(f"⏰ Started at: {start_time.strftime('%H:%M:%S')}")
        
        try:
            task_responses = await client.arun_tasks_until_done(task_data)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"✅ Completed at: {end_time.strftime('%H:%M:%S')} (took {duration:.1f}s)")
            
            # Process responses
            all_results = []
            for i, question in enumerate(questions_to_process):
                owl_response = task_responses[i]
                
                result = {
                    "question": question,
                    "owl_answer": owl_response.answer,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save to file with meaningful name
                file_path = self._save_result(result, i + 1, question)
                result["file_path"] = file_path
                
                all_results.append(result)
                
                print(f"\n📝 Question {i + 1}: {question[:80]}...")
                print(f"💾 Saved to: {file_path}")
            
            print(f"\n✅ Successfully processed {len(all_results)} questions")
            return all_results
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _save_result(self, result, question_num, question_text):
        """Save a single result to file with meaningful name."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create meaningful filename from question
        # Take first few words, clean them up
        words = question_text.lower().split()[:5]
        clean_words = []
        for word in words:
            # Remove special characters
            clean = ''.join(c for c in word if c.isalnum())
            if clean:
                clean_words.append(clean)
        
        meaningful_name = '_'.join(clean_words[:4])
        filename = f"q{question_num}_{meaningful_name}_{timestamp}.txt"
        file_path = os.path.join(self.output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("HYPOTHESIS VERIFICATION RESULT (OWL)\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Question: {result['question']}\n\n")
            f.write(f"Timestamp: {result['timestamp']}\n\n")
            
            f.write("-"*80 + "\n")
            f.write("OWL RESPONSE:\n")
            f.write("-"*80 + "\n")
            f.write(result['owl_answer'] + "\n\n")
        
        return file_path
    
    def verify_questions_sync(self, questions, batch_size=2, wait_time=0):
        """
        Synchronous wrapper for verify_batch.
        Only processes first 2 questions.
        
        Args:
            questions: List of question strings
            batch_size: Number of questions to process (default: 2)
            wait_time: Not used, kept for compatibility
            
        Returns:
            List of results
        """
        return asyncio.run(self.verify_batch(questions, batch_size, wait_time))
