import os
import hmac
import hashlib
import utils
from flask import Flask, request
from flask_restful import Resource, Api, reqparse

app = Flask(__name__)
api = Api(app)


# SEARCH_LIST = utils.generate_list_for_search(DATABASE)


# def return_results_hashable(query: str, threshold: int) -> list[dict]:
#     return utils.return_results(DATABASE, query, threshold, SEARCH_LIST)


class App(Resource):
    def __init__(self):
        self.bypasses, self.apps, self.db = utils.init_db(os.path.join('manifests'))

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('search', required=False)
        parser.add_argument('fields', required=False)

        args = parser.parse_args()
        if args.search is None:
            return {'status': 'Successful', 'data': self.apps}
        else:
            search_results = utils.return_results(self.db, args.search, 90)

            for index, res in enumerate(search_results):
                if res['bypasses']:
                    bypass_notes = list()
                    detailed_bypass_info = list()
                    downgrade_noted = False
                    for bypass in res['bypasses']:
                        if 'name' in bypass:
                            notes_from_bypass = self.bypasses[bypass['name']]['notes'] \
                                if 'notes' in self.bypasses[bypass['name']] \
                                else None
                            if 'guide' in self.bypasses[bypass['name']]:
                                bypass['guide'] = self.bypasses[bypass['name']]['guide']

                            if 'repository' in self.bypasses[bypass['name']]:
                                bypass['repository'] = self.bypasses[bypass['name']]['repository']
                                bypass['repository']['uri'] = f"https://sharerepo.stkc.win/?repo={self.bypasses[bypass['name']]['repository']['uri']}"
                            else:
                                bypass['repository'] = None

                            if not downgrade_noted and 'version' in bypass and bypass['name'] != "AppStore++":
                                bypass_notes.append(
                                    f"Use AppStore++ ({utils.markdown_link('repo', self.bypasses['AppStore++']['repository']['uri'], sharerepo=True)}) to downgrade.")
                                downgrade_noted = True

                            notes_from_bypass = f"{self.bypasses[bypass['name']]['notes']}" \
                                if 'notes' in self.bypasses[bypass['name']] \
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
                    os.system('git pull')
                    os.system('git submodule update --recursive --remote')
                    os.system(f'sudo /bin/systemctl restart {systemd_service}')
        else:
            return "Signatures didn't match!", 500


api.add_resource(App, '/app')
if 'GITHUB_WEBHOOK_SECRET' in os.environ:
    api.add_resource(GitHubWebhook, '/gh-webhook')


if __name__ == '__main__':
    app.run(debug=True)
