"""Skeleton (W1-I section 15): a create_app that returns 501 for every request. The reference arrives in the green commit."""

from microdot.wsgi import Microdot


def create_app(tokens, db_path):
    app = Microdot()

    @app.route('/<path:path>', methods=['GET', 'POST', 'DELETE'])
    async def not_implemented(request, path):
        return {'error': 'not implemented'}, 501

    return app
