def prune_serpapi_response(raw: dict) -> dict:
    """
    Given a full SerpAPI JSON response, returns a pared-down dict containing:
    - query
    - optional spelling suggestion
    - organic results (position, title, link, snippet, highlighted terms)
    - inline images (source URL and title)
    """
    pruned = {}

    # 1. Query and optional spelling suggestion
    params = raw.get("search_parameters", {})
    info   = raw.get("search_information", {})
    pruned["query"] = params.get("q", "")
    if "spelling_fix" in info:
        pruned["spelling_suggestion"] = info["spelling_fix"]

    # 2. Organic results
    pruned_results = []
    for item in raw.get("organic_results", []):
        pruned_results.append({
            "position":           item.get("position"),
            "title":              item.get("title"),
            "link":               item.get("link"),
            "snippet":            item.get("snippet"),
            "highlighted_terms":  item.get("snippet_highlighted_words", []),
        })
    pruned["results"] = pruned_results

    # 3. Inline images
    pruned_images = []
    for img in raw.get("inline_images", []):
        pruned_images.append({
            "source": img.get("source"),
            "title":  img.get("title"),
        })
    pruned["images"] = pruned_images

    return pruned