import os
import json
import yaml
from fuzzywuzzy import fuzz
from typing import Optional


def init_db(manifests_dir: str) -> tuple[dict, list, dict]:
    __scriptdir = os.path.dirname(os.path.realpath(__file__))
    bypasses_file = os.path.join(__scriptdir, manifests_dir, 'bypasses.yaml')
    apps_dir = os.path.join(__scriptdir, manifests_dir, 'apps')

    with open(bypasses_file, encoding='utf-8') as file:
        bypasses = yaml.safe_load(file)

    db_data = list()
    apps_files = [os.path.join(apps_dir, f) for f in os.listdir(apps_dir) if os.path.isfile(os.path.join(apps_dir, f)) and os.path.splitext(f)[-1].lower() == '.yaml']
    for app_file in apps_files:
        with open(app_file, encoding='utf-8') as file:
            app = yaml.safe_load(file.read())
        if app['bypasses']:
            bypass_notes = list()
            detailed_bypass_info = list()
            downgrade_noted = False
            for bypass in app['bypasses']:
                if 'name' in bypass:
                    notes_from_bypass = bypasses[bypass['name']]['notes'] \
                        if 'notes' in bypasses[bypass['name']] \
                        else None
                    if 'guide' in bypasses[bypass['name']]:
                        bypass['guide'] = bypasses[bypass['name']]['guide']

                    if 'repository' in bypasses[bypass['name']]:
                        bypass['repository'] = bypasses[bypass['name']]['repository']
                        bypass['repository']['uri'] = f"https://sharerepo.stkc.win/?repo={bypasses[bypass['name']]['repository']['uri']}" \
                            if not bypass['repository']['uri'].startswith("https://sharerepo.stkc.win/?repo=") \
                            else bypass['repository']['uri']
                    else:
                        bypass['repository'] = None

                    if not downgrade_noted and 'version' in bypass and bypass['name'] != "AppStore++":
                        bypass_notes.append(
                            f"Use AppStore++ ({markdown_link('repo', bypasses['AppStore++']['repository']['uri'], sharerepo=True)}) to downgrade.")
                        downgrade_noted = True

                    notes_from_bypass = f"{bypasses[bypass['name']]['notes']}" \
                        if 'notes' in bypasses[bypass['name']] \
                        else None
                    notes_from_manifest = bypass['notes'] \
                        if 'notes' in bypass \
                        else None
                    if notes_from_bypass or notes_from_manifest:
                        bypass_notes.append(' '.join(filter(None, [notes_from_bypass, notes_from_manifest])))
                    if bypass_notes:
                        bypass['notes'] = '\n'.join(bypass_notes)

                detailed_bypass_info.append(bypass)
            app['bypasses'] = detailed_bypass_info
            db_data.append(app)

    apps = [x['name'] for x in db_data]
    apps.sort(key=lambda a: a.lower())

    with open('database.json', 'w') as f:
        f.write(json.dumps({'app_list': apps, 'bypass_information': db_data}))


def markdown_link(name: str, uri: str, sharerepo: Optional[bool] = False) -> str:
    sharerepo_site = "https://sharerepo.stkc.win/?repo="
    return f"[{name}]({sharerepo_site}{uri})" if sharerepo else f"[{name}]({uri})"


def generate_list_for_search(list_of_dicts: list[dict]) -> list[list]:
    values = list()
    for item in list_of_dicts:
        values.append([item['name'].lower(), item['bundleId'].lower()])
    return values


def return_results(list_of_dicts: list[dict], query: str, threshold: int, list_for_search: Optional[list[list]] = None) -> list[dict]:
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
