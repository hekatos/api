import os
import orjson
import simdjson
import yaml
import concurrent.futures
from rapidfuzz import fuzz
from typing import Optional
from functools import cache


def init_db(manifests_dir: str) -> None:
    __scriptdir = os.path.dirname(os.path.realpath(__file__))
    bypasses_file = os.path.join(__scriptdir, manifests_dir, 'bypasses.yaml')
    apps_dir = os.path.join(__scriptdir, manifests_dir, 'apps')

    with open(bypasses_file, encoding='utf-8') as file:
        bypasses = yaml.safe_load(file)

    db_data = list()
    search_list = list()
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
                        bypass['repository']['uri'] = f"https://beerpsi.me/sharerepo/?repo={bypasses[bypass['name']]['repository']['uri']}" \
                            if not bypass['repository']['uri'].startswith("https://beerpsi.me/sharerepo/?repo=") \
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
        if 'aliases' in app and app['aliases']:
            temp = [app['name'].lower(), app['bundleId'].lower()]
            temp += [alias.lower() for alias in app['aliases']]
            search_list.append(temp)
        else:
            search_list.append([app['name'].lower(), app['bundleId'].lower()])
    apps = [x['name'] for x in db_data]
    apps.sort(key=lambda a: a.lower())

    with open('database.json', 'wb') as f:
        f.write(orjson.dumps({'app_list': apps, 'search_list': search_list, 'bypass_information': db_data}))
    markdown_link.cache_clear()


@cache
def markdown_link(name: str, uri: str, sharerepo: bool = False) -> str:
    sharerepo_site = "https://beerpsi.me/sharerepo/?repo="
    return f"[{name}]({sharerepo_site}{uri})" if sharerepo else f"[{name}]({uri})"


@cache
def generate_list_for_search(json_file: str) -> list[list]:
    with open(json_file, 'rb') as f:
        parser = simdjson.Parser()
        return parser.parse(f.read()).at_pointer('/search_list').as_list()  # type: ignore


async def return_results(list_of_dicts: simdjson.Array, query: str, threshold: int, list_for_search: Optional[list[list]] = None) -> list[dict]:
    def score_calculator(query: str, threshold: int, index: int, item: list[list]) -> Optional[dict]:
        ratios = list()
        partial_ratios = list()
        for value in item:
            ratios.append(fuzz.ratio(str(query), str(value)))
            partial_ratios.append(fuzz.partial_ratio(str(query), str(value)))
        partial_score = max(partial_ratios)
        score = max(ratios)
        if score >= threshold or partial_score >= threshold:
            return {"index": int(index), "partial_score": partial_score, "score": score}
        else:
            return None

    query = query.lower()
    scores = list()
    values = list_for_search if list_for_search else generate_list_for_search('database.json')
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        tasks = list()
        for index, item in enumerate(values):
            tasks.append(executor.submit(score_calculator, query, threshold, index, item))
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            if res:
                scores.append(res)

    sorted_filtered_scores = sorted(scores, key=lambda k: (k['score'], k['partial_score']), reverse=True)
    if len(sorted_filtered_scores) > 0 and sorted_filtered_scores[0]['score'] == 100:
        return [list_of_dicts.at_pointer(f"/{sorted_filtered_scores[0]['index']}").as_dict()]  # type: ignore
    filtered_list_of_dicts = [list_of_dicts.at_pointer(f"/{item['index']}").as_dict() for item in sorted_filtered_scores]  # type: ignore
    return filtered_list_of_dicts
