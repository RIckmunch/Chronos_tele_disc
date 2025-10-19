"""
Neo4j cleanup utilities for Chronos pipeline
Ensures isolated analysis for each image by clearing previous graph data
"""
from neo4j import GraphDatabase
from typing import Optional


def clear_neo4j_database(
    neo4j_url: str,
    neo4j_username: str,
    neo4j_password: str
) -> bool:
    """
    Clear all nodes and relationships from Neo4j database.

    This ensures that each image processing run has a clean graph database,
    preventing pattern discovery from finding patterns across multiple images.

    Args:
        neo4j_url: Neo4j connection URL (e.g., "neo4j://127.0.0.1:7687")
        neo4j_username: Neo4j username
        neo4j_password: Neo4j password

    Returns:
        True if successful, False otherwise
    """
    try:
        driver = GraphDatabase.driver(
            neo4j_url,
            auth=(neo4j_username, neo4j_password)
        )

        with driver.session() as session:
            # Delete all nodes and their relationships
            # DETACH DELETE ensures relationships are removed first
            result = session.run("MATCH (n) DETACH DELETE n")
            result.consume()

            # Verify cleanup was successful
            count_result = session.run("MATCH (n) RETURN count(n) as count")
            count = count_result.single()["count"]

            if count == 0:
                print("✅ Neo4j database cleared successfully (0 nodes remaining)")
                return True
            else:
                print(f"⚠️  Warning: {count} nodes still remain after cleanup attempt")
                return False

        driver.close()

    except Exception as e:
        print(f"❌ Error clearing Neo4j database: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_database_stats(
    neo4j_url: str,
    neo4j_username: str,
    neo4j_password: str
) -> Optional[dict]:
    """
    Get statistics about the current Neo4j database state.

    Useful for debugging and monitoring database growth.

    Args:
        neo4j_url: Neo4j connection URL
        neo4j_username: Neo4j username
        neo4j_password: Neo4j password

    Returns:
        Dictionary with node count, relationship count, and labels,
        or None if an error occurred
    """
    try:
        driver = GraphDatabase.driver(
            neo4j_url,
            auth=(neo4j_username, neo4j_password)
        )

        with driver.session() as session:
            # Count nodes
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]

            # Count relationships
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

            # Get all labels
            labels_result = session.run("CALL db.labels()")
            labels = [record["label"] for record in labels_result]

            return {
                "node_count": node_count,
                "relationship_count": rel_count,
                "labels": labels
            }

        driver.close()

    except Exception as e:
        print(f"❌ Error getting database stats: {e}")
        return None


if __name__ == "__main__":
    # Test the cleanup utility
    import os
    from dotenv import load_dotenv
    from pathlib import Path

    # Load environment variables
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    NEO4J_URL = os.environ.get("NEO4J_URL", "neo4j://127.0.0.1:7687")
    NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "0123456789")

    print("\n" + "="*80)
    print("NEO4J DATABASE CLEANUP UTILITY")
    print("="*80)

    # Get current stats
    print("\n📊 Current database state:")
    stats = get_database_stats(NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD)
    if stats:
        print(f"   Nodes: {stats['node_count']}")
        print(f"   Relationships: {stats['relationship_count']}")
        print(f"   Labels: {', '.join(stats['labels']) if stats['labels'] else 'None'}")

    # Confirm before clearing
    if stats and stats['node_count'] > 0:
        response = input(f"\n⚠️  This will delete {stats['node_count']} nodes and {stats['relationship_count']} relationships. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cleanup cancelled")
            exit(0)

    # Clear database
    print("\n🧹 Clearing database...")
    success = clear_neo4j_database(NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD)

    if success:
        print("\n✅ Database cleared successfully!")

        # Verify
        print("\n📊 Verifying database state:")
        stats = get_database_stats(NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD)
        if stats:
            print(f"   Nodes: {stats['node_count']}")
            print(f"   Relationships: {stats['relationship_count']}")
    else:
        print("\n❌ Database cleanup failed!")

    print("\n" + "="*80)
