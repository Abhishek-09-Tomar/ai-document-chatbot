def expand_query(query):
    expansions = [
        query,
        f"Explain {query}",
        f"What is {query}",
        f"Details about {query}"
    ]
    return expansions
