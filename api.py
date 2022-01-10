import os
import yaml
import hmac
import hashlib
import utils
from flask import Flask, request
from flask_restful import Resource, Api, reqparse
from functools import lru_cache

app = Flask(__name__)
api = Api(app)


def init_db(manifests_dir):
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
        db_data.append(app)
    apps = [x['name'] for x in db_data]
    apps.sort(key=lambda a: a.lower())
    return bypasses, apps, db_data


bypasses, apps, db = init_db(os.path.join('manifests'))
search_list = utils.generate_list_for_search(db)


@lru_cache(maxsize=16)
def return_results_hashable(query, threshold):
    return utils.return_results(db, query, threshold, search_list)

@app.route('/app', methods=['GET'])
def get_bypass_for_app():
    parser = reqparse.RequestParser()
    parser.add_argument('search', required=False)
    parser.add_argument('fields', required=False)

    args = parser.parse_args()
    if args.search is None:
        return {'status': 'Successful', 'data': apps}
    else:
        search_results = return_results_hashable(args.search.lower(), 90)

        for index, res in enumerate(search_results):
            if res['bypasses']:
                bypass_notes = list()
                detailed_bypass_info = list()
                downgrade_noted = False
                for bypass in res['bypasses']:
                    if 'name' in bypass:
                        notes_from_bypass = bypasses[bypass['name']]['notes'] \
                                            if 'notes' in bypasses[bypass['name']] \
                                            else None
                        if 'guide' in bypasses[bypass['name']]:
                            bypass['guide'] = bypasses[bypass['name']]['guide']

                        if 'repository' in bypasses[bypass['name']]:
                            bypass['repository'] = bypasses[bypass['name']]['repository']
                            bypass['repository']['uri'] = f"https://sharerepo.stkc.win/?repo={bypasses[bypass['name']]['repository']['uri']}"
                        else:
                            bypass['repository'] = None

                        if not downgrade_noted and 'version' in bypass and bypass['name'] != "AppStore++":
                            bypass_notes.append(
                                f"Use AppStore++ ({utils.markdown_link('repo', bypasses['AppStore++']['repository']['uri'], sharerepo=True)}) to downgrade.")
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
                search_results[index]['bypasses'] = detailed_bypass_info

        if search_results:
            return {'status': 'Successful', 'data': search_results}
        else:
            return {'status': 'Not Found'}


class GitHubWebhook(Resource):
    def __init__(self):
        self.webhook_secret = os.environ.get('GITHUB_WEBHOOK_SECRET').encode('utf-8')

    def post(self):
        signature = 'sha256=' + hmac.new(self.webhook_secret, request.data, hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, request.headers.get('X-Hub-Signature-256')):
            content = request.json
            if content['ref'] == 'refs/heads/main':
                try:
                    return "Restarting API...", 200
                finally:
                    systemd_service = 'jbdetectapi'
                    os.system(f'git pull')
                    os.system(f'git submodule update --recursive --remote')
                    os.system(f'sudo /bin/systemctl restart {systemd_service}')
        else:
            return "Signatures didn't match!", 500


if 'GITHUB_WEBHOOK_SECRET' in os.environ:
    api.add_resource(GitHubWebhook, '/gh-webhook')


if __name__ == '__main__':
    app.run(debug=True)



