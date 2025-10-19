"""
Utility functions for verifying and analyzing Neo4j knowledge graphs
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any, Optional
import json


class Neo4jVerifier:
    """
    Utility class to verify and analyze knowledge graphs in Neo4j.
    """
    
    def __init__(self, uri: str = "neo4j://127.0.0.1:7687", 
                 username: str = "neo4j", 
                 password: str = "0123456789"):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j URI
            username: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        print(f"✅ Connected to Neo4j at {uri}")
    
    def close(self):
        """Close the database connection."""
        self.driver.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get basic statistics about the knowledge graph.
        
        Returns:
            Dictionary with node count, relationship count, and label counts
        """
        with self.driver.session() as session:
            # Count nodes
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            
            # Count relationships
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            
            # Get node labels and their counts
            labels_query = """
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
            """
            labels_result = session.run(labels_query)
            labels = {record["label"]: record["count"] for record in labels_result}
            
            # Get relationship types and their counts
            rel_query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY count DESC
            """
            rel_result = session.run(rel_query)
            relationships = {record["type"]: record["count"] for record in rel_result}
            
            return {
                "total_nodes": node_count,
                "total_relationships": rel_count,
                "node_labels": labels,
                "relationship_types": relationships
            }
    
    def print_stats(self):
        """Print formatted statistics about the knowledge graph."""
        stats = self.get_stats()
        
        print("\n" + "="*80)
        print("📊 NEO4J KNOWLEDGE GRAPH STATISTICS")
        print("="*80)
        print(f"\n📈 Overview:")
        print(f"   Total Nodes: {stats['total_nodes']:,}")
        print(f"   Total Relationships: {stats['total_relationships']:,}")
        
        if stats['node_labels']:
            print(f"\n🏷️  Node Labels:")
            for label, count in sorted(stats['node_labels'].items(), key=lambda x: x[1], reverse=True):
                print(f"   {label}: {count:,}")
        else:
            print(f"\n⚠️  No nodes found in the database!")
        
        if stats['relationship_types']:
            print(f"\n🔗 Relationship Types:")
            for rel_type, count in sorted(stats['relationship_types'].items(), key=lambda x: x[1], reverse=True):
                print(f"   {rel_type}: {count:,}")
        else:
            print(f"\n⚠️  No relationships found in the database!")
        
        print("="*80 + "\n")
    
    def get_sample_nodes(self, label: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Get sample nodes from the graph.
        
        Args:
            label: Optional node label to filter by
            limit: Number of nodes to return
        
        Returns:
            List of node dictionaries
        """
        with self.driver.session() as session:
            if label:
                query = f"""
                MATCH (n:{label})
                RETURN n
                LIMIT {limit}
                """
            else:
                query = f"""
                MATCH (n)
                RETURN n
                LIMIT {limit}
                """
            
            result = session.run(query)
            nodes = []
            for record in result:
                node = record["n"]
                nodes.append({
                    "labels": list(node.labels),
                    "properties": dict(node)
                })
            return nodes
    
    def print_sample_nodes(self, label: Optional[str] = None, limit: int = 5):
        """Print sample nodes in a readable format."""
        nodes = self.get_sample_nodes(label, limit)
        
        if not nodes:
            print(f"⚠️  No nodes found{' with label: ' + label if label else ''}!")
            return
        
        print(f"\n📋 Sample Nodes{' (' + label + ')' if label else ''} (showing {len(nodes)}):")
        print("="*80)
        
        for i, node in enumerate(nodes, 1):
            print(f"\n{i}. Labels: {', '.join(node['labels'])}")
            for key, value in node['properties'].items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                print(f"   {key}: {value}")
    
    def search_nodes(self, property_name: str, search_value: str, limit: int = 10) -> List[Dict]:
        """
        Search for nodes by property value.
        
        Args:
            property_name: Property to search in
            search_value: Value to search for (case-insensitive contains)
            limit: Maximum results
        
        Returns:
            List of matching nodes
        """
        with self.driver.session() as session:
            query = f"""
            MATCH (n)
            WHERE toLower(toString(n.{property_name})) CONTAINS toLower($value)
            RETURN n
            LIMIT {limit}
            """
            result = session.run(query, value=search_value)
            nodes = []
            for record in result:
                node = record["n"]
                nodes.append({
                    "labels": list(node.labels),
                    "properties": dict(node)
                })
            return nodes
    
    def get_node_relationships(self, node_id: str) -> Dict[str, Any]:
        """
        Get all relationships for a specific node.
        
        Args:
            node_id: Node ID or property to match
        
        Returns:
            Dictionary with node info and relationships
        """
        with self.driver.session() as session:
            query = """
            MATCH (n)
            WHERE id(n) = $node_id OR n.id = $node_id OR n.name = $node_id
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN n, collect({type: type(r), target: m}) as relationships
            LIMIT 1
            """
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record:
                return None
            
            node = record["n"]
            relationships = record["relationships"]
            
            return {
                "node": {
                    "labels": list(node.labels),
                    "properties": dict(node)
                },
                "relationships": [
                    {
                        "type": rel["type"],
                        "target": {
                            "labels": list(rel["target"].labels) if rel["target"] else [],
                            "properties": dict(rel["target"]) if rel["target"] else {}
                        }
                    }
                    for rel in relationships if rel["target"]
                ]
            }
    
    def check_document_chunks(self, element_id_prefix: str = "") -> Dict[str, Any]:
        """
        Check if document chunks are properly stored.
        
        Args:
            element_id_prefix: Prefix of element IDs to search for
        
        Returns:
            Information about found chunks
        """
        with self.driver.session() as session:
            if element_id_prefix:
                query = """
                MATCH (n)
                WHERE n.element_id STARTS WITH $prefix
                RETURN count(n) as chunk_count, collect(n.element_id) as chunk_ids
                """
                result = session.run(query, prefix=element_id_prefix)
            else:
                query = """
                MATCH (n)
                WHERE n.element_id IS NOT NULL
                RETURN count(n) as chunk_count, collect(n.element_id) as chunk_ids
                """
                result = session.run(query)
            
            record = result.single()
            return {
                "chunk_count": record["chunk_count"],
                "chunk_ids": record["chunk_ids"]
            }
    
    def clear_database(self, confirm: bool = False):
        """
        Clear all nodes and relationships from the database.
        
        Args:
            confirm: Must be True to actually delete
        """
        if not confirm:
            print("⚠️  WARNING: This will delete ALL data from Neo4j!")
            print("   Call with confirm=True to proceed")
            return
        
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("✅ Database cleared")
    
    def export_to_json(self, output_file: str = "neo4j_export.json"):
        """
        Export the entire graph to JSON.
        
        Args:
            output_file: Output JSON file path
        """
        with self.driver.session() as session:
            # Export nodes
            nodes_query = """
            MATCH (n)
            RETURN id(n) as id, labels(n) as labels, properties(n) as properties
            """
            nodes_result = session.run(nodes_query)
            nodes = [dict(record) for record in nodes_result]
            
            # Export relationships
            rels_query = """
            MATCH (n)-[r]->(m)
            RETURN id(n) as source, type(r) as type, id(m) as target, properties(r) as properties
            """
            rels_result = session.run(rels_query)
            relationships = [dict(record) for record in rels_result]
            
            export_data = {
                "nodes": nodes,
                "relationships": relationships
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Exported {len(nodes)} nodes and {len(relationships)} relationships to {output_file}")


# Convenience functions
def verify_knowledge_graph(uri: str = "neo4j://127.0.0.1:7687",
                          username: str = "neo4j",
                          password: str = "0123456789",
                          show_samples: bool = True):
    """
    Quick verification of knowledge graph.
    
    Args:
        uri: Neo4j URI
        username: Neo4j username
        password: Neo4j password
        show_samples: Show sample nodes
    """
    with Neo4jVerifier(uri, username, password) as verifier:
        verifier.print_stats()
        
        stats = verifier.get_stats()
        if stats['total_nodes'] == 0:
            print("❌ No knowledge graph found in Neo4j!")
            print("\n   Possible issues:")
            print("   1. Document text was too large and got truncated")
            print("   2. Knowledge graph extraction failed")
            print("   3. Neo4j connection issue")
            print("   4. Token limit exceeded during processing")
            print("\n   Solutions:")
            print("   - Check if text extraction was successful")
            print("   - Enable chunking: enable_chunking=True")
            print("   - Reduce chunk size: kg_chunk_size=10000")
            print("   - Check Neo4j logs for errors")
            return False
        
        if show_samples and stats['node_labels']:
            # Show samples from the most common label
            top_label = max(stats['node_labels'].items(), key=lambda x: x[1])[0]
            verifier.print_sample_nodes(label=top_label, limit=3)
        
        return True


def check_chunking_status(element_id: str = "0",
                          uri: str = "neo4j://127.0.0.1:7687",
                          username: str = "neo4j",
                          password: str = "0123456789"):
    """
    Check if document was processed in chunks.
    
    Args:
        element_id: Document element ID prefix
        uri: Neo4j URI
        username: Neo4j username
        password: Neo4j password
    """
    with Neo4jVerifier(uri, username, password) as verifier:
        chunk_info = verifier.check_document_chunks(element_id)
        
        print("\n" + "="*80)
        print("📦 DOCUMENT CHUNKING STATUS")
        print("="*80)
        print(f"\nElement ID prefix: '{element_id}'")
        print(f"Chunks found: {chunk_info['chunk_count']}")
        
        if chunk_info['chunk_count'] > 0:
            print(f"\nChunk IDs:")
            for chunk_id in chunk_info['chunk_ids'][:10]:  # Show first 10
                print(f"   - {chunk_id}")
            if chunk_info['chunk_count'] > 10:
                print(f"   ... and {chunk_info['chunk_count'] - 10} more")
            return True
        else:
            print("\n⚠️  No chunks found with this element ID")
            return False


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*80)
    print("NEO4J KNOWLEDGE GRAPH VERIFIER")
    print("="*80)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "verify":
            verify_knowledge_graph()
        
        elif command == "stats":
            with Neo4jVerifier() as verifier:
                verifier.print_stats()
        
        elif command == "sample":
            label = sys.argv[2] if len(sys.argv) > 2 else None
            with Neo4jVerifier() as verifier:
                verifier.print_sample_nodes(label=label)
        
        elif command == "chunks":
            element_id = sys.argv[2] if len(sys.argv) > 2 else "0"
            check_chunking_status(element_id)
        
        elif command == "search":
            if len(sys.argv) < 4:
                print("Usage: python neo4j_utils.py search <property> <value>")
                sys.exit(1)
            prop = sys.argv[2]
            value = sys.argv[3]
            with Neo4jVerifier() as verifier:
                results = verifier.search_nodes(prop, value)
                print(f"\n🔍 Found {len(results)} nodes:")
                for i, node in enumerate(results, 1):
                    print(f"\n{i}. {node['labels']}")
                    print(f"   {node['properties']}")
        
        elif command == "export":
            output = sys.argv[2] if len(sys.argv) > 2 else "neo4j_export.json"
            with Neo4jVerifier() as verifier:
                verifier.export_to_json(output)
        
        elif command == "clear":
            print("⚠️  WARNING: This will delete ALL data!")
            confirm = input("Type 'DELETE' to confirm: ")
            if confirm == "DELETE":
                with Neo4jVerifier() as verifier:
                    verifier.clear_database(confirm=True)
            else:
                print("Cancelled")
        
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  verify  - Verify KG and show stats")
            print("  stats   - Show statistics only")
            print("  sample [label] - Show sample nodes")
            print("  chunks [element_id] - Check document chunks")
            print("  search <property> <value> - Search nodes")
            print("  export [file] - Export to JSON")
            print("  clear   - Clear database")
    
    else:
        # Default: run verification
        verify_knowledge_graph()