"""
Knowledge Graph Pattern Discovery Module
Discovers patterns in Neo4j and generates questions using OpenAI
"""

from neo4j import GraphDatabase
import itertools
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import os

# Load environment from parent .env file (telegram-bot/.env)
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class KGPatternDiscovery:
    """Discovers patterns in knowledge graph and generates questions."""
    
    def __init__(self, neo4j_url, neo4j_username, neo4j_password, openai_api_key=None):
        """Initialize with Neo4j and OpenAI credentials."""
        self.driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_username, neo4j_password))
        self.client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
    
    def generate_question(self, pattern_info, relationships):
        """Generate a natural language question based on the pattern using OpenAI API."""
        path_steps = []
        for info in pattern_info:
            path_steps.append(f"{info['from']} --[{info['rel']}]--> {info['to']}")
        path_description = "\n   ".join(path_steps)
        
        prompt = f"""Generate a natural language question based on this graph database pattern.

Pattern relationships: {' -> '.join(relationships)}

Actual path found:
   {path_description}

IMPORTANT: Use the EXACT relationship names in the question. Convert them to natural language by:
- Replacing underscores with spaces
- Making them lowercase
- Keeping the relationship verb/phrase intact

Examples of correct format:

Example 1:
Path: lying_position --[FOLLOWED_BY]--> sitting_limitations
Question: "Has lying position followed by sitting limitations?"

Example 2:
Path: hip_joint_position --[RESPONDS_TO]--> normal_posture
      normal_posture --[DESCRIBED_IN]--> Parow
Question: "Has hip joint position responds to normal posture and also described in Parow?"

Example 3:
Path: entity1 --[CAUSES]--> entity2 --[LEADS_TO]--> entity3
Question: "Has entity1 causes entity2 and leads to entity3?"

Generate the question following this exact pattern. Use the relationship names as verbs/phrases in the question.
Return ONLY the question, nothing else."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an assistant that converts graph database patterns into natural language questions. Always use the exact relationship names as verbs in the questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating question: {e}")
            return None
    
    def discover_patterns(self, max_length=3, max_patterns_per_length=5):
        """
        Discover patterns in the knowledge graph and generate questions.
        
        Args:
            max_length: Maximum relationship chain length
            max_patterns_per_length: Maximum patterns to test per length
            
        Returns:
            List of dictionaries with pattern, example_path, question, num_paths
        """
        print("\n🔍 Discovering relationship types...")
        
        with self.driver.session() as session:
            rel_result = session.run("CALL db.relationshipTypes()")
            relationships = [record["relationshipType"] for record in rel_result]
        
        print(f"✅ Found {len(relationships)} relationships: {relationships}")
        
        # Generate patterns
        print(f"\n🔄 Generating patterns up to length {max_length}...")
        patterns = []
        for r in range(1, min(max_length, len(relationships)) + 1):
            count = 0
            for subset in itertools.combinations(relationships, r):
                for perm in itertools.permutations(subset):
                    patterns.append(perm)
                    count += 1
                    if count >= max_patterns_per_length:
                        break
                if count >= max_patterns_per_length:
                    break
        
        print(f"✅ Generated {len(patterns)} patterns")
        
        # Query Neo4j and generate questions
        print("\n" + "="*80)
        print("🚀 Starting Pattern Analysis with Question Generation")
        print("="*80)
        
        results_summary = []
        
        with self.driver.session() as session:
            for idx, rels in enumerate(patterns, 1):
                pattern = "-[:{}]->".format("]->()-[:".join(rels))
                query = f"""
                MATCH path = (start){pattern}(end)
                RETURN [i IN range(0, size(relationships(path))-1) |
                {{
                    from: coalesce(nodes(path)[i].id, nodes(path)[i].name, labels(nodes(path)[i])[0]),
                    rel: type(relationships(path)[i]),
                    to: coalesce(nodes(path)[i+1].id, nodes(path)[i+1].name, labels(nodes(path)[i+1])[0])
                }}] AS connections
                LIMIT 5
                """
                
                result = session.run(query)
                rows = list(result)
                
                if rows:
                    print(f"\n{'='*80}")
                    print(f"🔹 Pattern {idx}/{len(patterns)}: {' → '.join(rels)}")
                    print(f"{'='*80}")
                    
                    first_example = rows[0]["connections"]
                    print("\n📍 Example path:")
                    for conn in first_example:
                        print(f"   {conn['from']} --[{conn['rel']}]--> {conn['to']}")
                    
                    print("\n🤖 Generating question...")
                    question = self.generate_question(first_example, rels)
                    
                    if question:
                        print(f"\n❓ Generated Question:")
                        print(f"   {question}")
                        
                        results_summary.append({
                            "pattern": rels,
                            "example_path": first_example,
                            "question": question,
                            "num_paths": len(rows)
                        })
                    
                    print(f"\n📊 Found {len(rows)} matching paths for this pattern")
        
        print("\n" + "="*80)
        print("📋 PATTERN DISCOVERY SUMMARY")
        print("="*80)
        print(f"Total patterns analyzed: {len(patterns)}")
        print(f"Patterns with matches: {len(results_summary)}")
        print(f"Questions generated: {len([r for r in results_summary if r['question']])}")
        
        return results_summary
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()
