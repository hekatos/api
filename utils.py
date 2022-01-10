from fuzzywuzzy import fuzz


def markdown_link(name, uri, sharerepo=False):
    sharerepo_site = "https://sharerepo.stkc.win/?repo="
    return f"[{name}]({sharerepo_site}{uri})" if sharerepo else f"[{name}]({uri})"


def generate_list_for_search(list_of_dicts):
    values = list()
    for item in list_of_dicts:
        values.append([item['name'].lower(), item['bundleId'].lower()])
    return values


def return_results(list_of_dicts, query, threshold, list_for_search=None):
    query = query.lower()
    scores = list()
    values = list_for_search if list_for_search else generate_list_for_search(list_of_dicts)
    for index, item in enumerate(values):
        ratios = [fuzz.ratio(str(query), str(value)) for value in item]
        partial_ratios = [fuzz.partial_ratio(str(query), str(value)) for value in item]  # ensure both are in string
        scores.append({"index": index, "partial_score": max(partial_ratios), "score": max(ratios)})

    filtered_scores = [item for item in scores if item['score'] >= threshold or item['partial_score'] >= threshold]
    sorted_filtered_scores = sorted(filtered_scores, key=lambda k: (k['score'], k['partial_score']), reverse=True)
    if len(sorted_filtered_scores) > 0 and sorted_filtered_scores[0]['score'] == 100:
        return [list_of_dicts[sorted_filtered_scores[0]['index']]]
    filtered_list_of_dicts = [list_of_dicts[item["index"]] for item in sorted_filtered_scores]
    return filtered_list_of_dicts
