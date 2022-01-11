import os
import hmac
import hashlib
import utils
import orjson
from flask import Flask, request
from flask_restful import Resource, Api, reqparse
from cachetools.func import ttl_cache

app = Flask(__name__)
api = Api(app)
utils.init_db(os.path.join('manifests'))


@ttl_cache(maxsize=64, ttl=3600)
def return_results_hashable(query: str, threshold: int) -> list[dict]:
    with open('database.json', 'rb') as f:
        database = orjson.loads(f.read())['bypass_information']
        return utils.return_results(database, query, threshold, utils.generate_list_for_search('database.json'))


class App(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('search', required=False)
        parser.add_argument('fields', required=False)

        args = parser.parse_args()
        if args.search is None:
            with open('database.json', 'rb') as f:
                return {'status': 'Successful', 'data': orjson.loads(f.read())['app_list']}
        else:
            search_results = return_results_hashable(args.search.lower(), 90)
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
                if 'manifests' in content['repository']['full_name']:
                    os.system('git submodule update --recursive --remote')
                    utils.init_db(os.path.join('manifests'))
                    utils.generate_list_for_search.cache_clear()
                    return_results_hashable.cache_clear()
                    return "Rebuilt database", 200
                elif 'api' in content['repository']['full_name']:
                    systemd_service = 'jbdetectapi'
                    os.system('git pull')
                    os.system(f'sudo /bin/systemctl restart {systemd_service}')
        else:
            return "Signatures didn't match!", 500


api.add_resource(App, '/app')
if 'GITHUB_WEBHOOK_SECRET' in os.environ:
    api.add_resource(GitHubWebhook, '/gh-webhook')


if __name__ == '__main__':
    app.run(debug=True)
