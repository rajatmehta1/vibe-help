"""Test script for the KnowledgeGraphManager.

Requires a running Neo4j instance:
  docker compose up -d neo4j

Run from backend/:
  python -m scripts.test_knowledge_graph
"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.core.knowledge import KnowledgeGraphManager

TEST_PROJECT_ID = "test-project-001"


async def main() -> None:
    gm = KnowledgeGraphManager()

    # 1. Verify connection
    print("1. Verifying Neo4j connection...")
    try:
        status = await gm.verify_connection()
        print(f"   Connected: {status}")
    except Exception as e:
        print(f"   FAILED to connect: {e}")
        print("   Make sure Neo4j is running: docker compose up -d neo4j")
        await gm.close()
        return

    # 2. Ensure indexes
    print("2. Ensuring indexes...")
    await gm.ensure_indexes()
    print("   Indexes created")

    # 3. Clean up any previous test data
    print("3. Clearing previous test data...")
    await gm.clear_project(TEST_PROJECT_ID)
    print("   Cleared")

    # 4. Create a mock project with files
    print("4. Creating mock project with files...")
    await gm.upsert_file(TEST_PROJECT_ID, {
        "id": "file-main",
        "path": "src/main.py",
        "language": "python",
        "content_hash": "abc123",
        "lines_of_code": 150,
        "ai_generated_ratio": 0.3,
    })
    await gm.upsert_file(TEST_PROJECT_ID, {
        "id": "file-utils",
        "path": "src/utils.py",
        "language": "python",
        "content_hash": "def456",
        "lines_of_code": 80,
        "ai_generated_ratio": 0.5,
    })
    await gm.upsert_file(TEST_PROJECT_ID, {
        "id": "file-models",
        "path": "src/models.py",
        "language": "python",
        "content_hash": "ghi789",
        "lines_of_code": 200,
        "ai_generated_ratio": 0.0,
    })
    print("   Created 3 files")

    # 5. Add functions to files
    print("5. Adding functions...")
    await gm.upsert_code_unit("file-main", "function", {
        "id": "fn-main-run",
        "name": "run_server",
        "params_json": '["host", "port"]',
        "return_type": "None",
        "is_async": True,
        "is_exported": True,
        "complexity": 5,
        "line_start": 10,
        "line_end": 30,
    })
    await gm.upsert_code_unit("file-main", "function", {
        "id": "fn-main-init",
        "name": "initialize_app",
        "params_json": '["config"]',
        "return_type": "App",
        "is_async": True,
        "is_exported": True,
        "complexity": 3,
        "line_start": 35,
        "line_end": 50,
    })
    await gm.upsert_code_unit("file-utils", "function", {
        "id": "fn-utils-parse",
        "name": "parse_config",
        "params_json": '["path"]',
        "return_type": "dict",
        "is_async": False,
        "is_exported": True,
        "complexity": 2,
        "line_start": 5,
        "line_end": 20,
    })
    await gm.upsert_code_unit("file-utils", "function", {
        "id": "fn-utils-validate",
        "name": "validate_input",
        "params_json": '["data", "schema"]',
        "return_type": "bool",
        "is_async": False,
        "is_exported": True,
        "complexity": 4,
        "line_start": 25,
        "line_end": 45,
    })
    await gm.upsert_code_unit("file-models", "function", {
        "id": "fn-models-create",
        "name": "create_user",
        "params_json": '["email", "name"]',
        "return_type": "User",
        "is_async": True,
        "is_exported": True,
        "complexity": 3,
        "line_start": 50,
        "line_end": 70,
    })
    print("   Created 5 functions")

    # 6. Set up CALLS relationships
    print("6. Setting up call relationships...")
    await gm.set_relationships(
        file_id="file-main",
        calls=[
            {"caller_id": "fn-main-run", "callee_id": "fn-main-init"},
            {"caller_id": "fn-main-init", "callee_id": "fn-utils-parse"},
            {"caller_id": "fn-main-init", "callee_id": "fn-utils-validate"},
            {"caller_id": "fn-main-run", "callee_id": "fn-models-create"},
        ],
        imports=[
            {"target_file_id": "file-utils", "imported_names": ["parse_config", "validate_input"]},
            {"target_file_id": "file-models", "imported_names": ["create_user"]},
        ],
    )
    print("   Call graph and imports set")

    # 7. Mark a function as AI-generated
    print("7. Marking AI-generated code...")
    await gm.mark_ai_generated("fn-utils-validate", source="copilot", confidence=0.85)
    await gm.mark_ai_generated("fn-models-create", source="claude", confidence=0.92)
    print("   Marked 2 functions as AI-generated")

    # 8. Query function callers
    print("\n--- Read Operations ---\n")

    print("8. Who calls parse_config?")
    callers = await gm.get_function_callers("fn-utils-parse")
    for c in callers:
        print(f"   {c['function']['name']} (from {c['file_path']})")

    print("9. What does run_server call?")
    callees = await gm.get_function_callees("fn-main-run")
    for c in callees:
        print(f"   {c['function']['name']} (from {c['file_path']})")

    # 9. Project stats
    print("10. Project stats:")
    stats = await gm.get_project_stats(TEST_PROJECT_ID)
    for k, v in stats.items():
        print(f"   {k}: {v}")

    # 10. Import graph
    print("11. Import graph:")
    imports = await gm.get_import_graph(TEST_PROJECT_ID)
    for imp in imports:
        print(f"   {imp['source']} -> {imp['target']} ({imp['imported_names']})")

    # 11. File graph
    print("12. File graph for main.py:")
    fg = await gm.get_file_graph("file-main")
    if fg:
        print(f"   File: {fg['file'].get('path')}")
        print(f"   Units: {[u.get('name') for u in fg['units']]}")
        print(f"   Imports: {[i['file'].get('path') for i in fg['imports'] if i['file']]}")

    # 12. AI generated code
    print("13. AI-generated code:")
    ai_code = await gm.get_ai_generated_code(TEST_PROJECT_ID)
    for item in ai_code:
        print(f"   {item['function']['name']} — source={item['ai_source']}, "
              f"confidence={item['confidence']}, status={item['review_status']}")

    # 13. Similar functions
    print("14. Functions similar to 'validate':")
    similar = await gm.get_similar_functions(TEST_PROJECT_ID, "validate")
    for s in similar:
        print(f"   {s['function']['name']} (from {s['file_path']})")

    # 14. Clean up
    print("\n15. Cleaning up test data...")
    await gm.clear_project(TEST_PROJECT_ID)
    print("   Done!")

    await gm.close()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
