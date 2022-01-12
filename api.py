import os
import hmac
import hashlib
import utils
import orjson
import simdjson
from flask import Flask, request
from flask_restful import reqparse
from cachetools.func import ttl_cache

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['JSON_AS_ASCII'] = False


utils.init_db(os.path.join('manifests'))
jsonparser = simdjson.Parser()


@ttl_cache(maxsize=128, ttl=3600)
def return_results_hashable(query: str, threshold: int) -> list[dict]:
    with open('database.json', 'rb') as f:
        database = jsonparser.parse(f.read()).at_pointer('/bypass_information')
        return utils.return_results(database, query, threshold, utils.generate_list_for_search('database.json'))


@app.route('/app', methods=["GET"])
def bypass_lookup():
    reqparser = reqparse.RequestParser()
    reqparser.add_argument('search', required=False)

    args = reqparser.parse_args()
    if args.search is None:
        with open('database.json', 'rb') as f:
            data = orjson.dumps({'status': 'Successful', 'data': jsonparser.parse(f.read()).at_pointer('/app_list').as_list()})
    else:
        search_results = return_results_hashable(args.search.lower(), 90)
        if search_results:
            data = orjson.dumps({'status': 'Successful', 'data': search_results})
        else:
            data = orjson.dumps({'status': 'Not Found'})

    return app.response_class(
        response=data,
        status=404 if b'Not Found' in data else 200,
        mimetype="application/json; charset=utf-8"
    )


@app.route('/gh-webhook', methods=["POST"])
def update_api():
    if 'GITHUB_WEBHOOK_SECRET' in os.environ:
        webhook_secret = os.environ.get('GITHUB_WEBHOOK_SECRET').encode('utf-8')
        signature = 'sha256=' + hmac.new(webhook_secret, request.data, hashlib.sha256).hexdigest()
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
                    try:
                        return "Restarting API", 200
                    finally:
                        systemd_service = 'jbdetectapi'
                        os.system('git pull')
                        os.system(f'sudo /bin/systemctl restart {systemd_service}')
        else:
            return "Signatures didn't match!", 500
    else:
        return "Endpoint disabled due to lack of GITHUB_WEBHOOK_SECRET", 403


if __name__ == '__main__':
    app.run(debug=True)
