import unittest
from test_api_access import app
from fastapi.testclient import TestClient


class PollTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, base_url="https://testserver")
        self.client.post('/auth/unlock', json={'password': 'RobiJeCar'})
        result = self.client.post('/auth/login', json={'username': 'test-admin', 'password': 'test-admin-password'})
        self.admin = {'Authorization': 'Bearer ' + result.json()['token']}
        self.body = {'title': 'Organizacija', 'questions': [
            {'text': 'Kateri dan?', 'options': ['Torek', 'Četrtek', 'Petek']},
            {'text': 'Katera ura?', 'options': ['19:00', '20:00']},
        ]}

    def tearDown(self):
        self.client.close()

    def create(self):
        result = self.client.post('/admin/polls', headers=self.admin, json=self.body)
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()['id']

    def test_full_lifecycle_and_result_access(self):
        poll_id = self.create()
        self.assertIn(poll_id, [p['id'] for p in self.client.get('/polls/active').json()])
        poll = next(p for p in self.client.get('/polls/active').json() if p['id'] == poll_id)
        self.assertNotIn('counts', poll)
        self.assertNotIn('submissions', poll)
        self.assertEqual(self.client.get(f'/polls/{poll_id}/results').status_code, 403)
        first = self.client.post(f'/polls/{poll_id}/vote', json={'name': '  Ana  Novak ', 'answers': [2, 0]})
        self.assertEqual(first.status_code, 201, first.text)
        token = first.json()['token']
        self.assertEqual(first.json()['results']['counts'], [[0, 0, 1], [1, 0]])
        second = self.client.post(f'/polls/{poll_id}/vote', json={'name': 'Bojan', 'answers': [0, 1]})
        self.assertEqual(second.status_code, 201)
        result = self.client.get(f'/polls/{poll_id}/results', headers={'X-Poll-Token': token})
        self.assertEqual(result.json()['total'], 2)
        self.assertNotIn('submissions', result.json())
        self.assertNotIn('Ana Novak', result.text)
        report = next(p for p in self.client.get('/admin/polls', headers=self.admin).json() if p['id'] == poll_id)
        self.assertEqual(report['submissions'][0]['name'], 'Ana Novak')
        self.assertEqual(report['submissions'][0]['answers'], [2, 0])
        self.assertTrue(report['created_at'].endswith('+00:00'))
        self.assertTrue(report['submissions'][0]['created_at'].endswith('+00:00'))
        self.assertNotIn('token', report['submissions'][0])
        self.assertEqual(self.client.post(f'/admin/polls/{poll_id}/archive', headers=self.admin).status_code, 200)
        self.assertNotIn(poll_id, [p['id'] for p in self.client.get('/polls/active').json()])
        self.assertEqual(self.client.get(f'/polls/{poll_id}/results', headers={'X-Poll-Token': token}).status_code, 404)
        self.assertEqual(self.client.post(f'/polls/{poll_id}/vote', json={'name': 'Cene', 'answers': [0, 0]}).status_code, 404)
        archive = next(p for p in self.client.get('/admin/polls', headers=self.admin).json() if p['id'] == poll_id)
        self.assertFalse(archive['active'])
        self.assertIsNotNone(archive['archived_at'])
        self.assertEqual(archive['total'], 2)

    def test_validation_and_duplicate_name(self):
        poll_id = self.create()
        for name, answers in [(' ', [0, 0]), ('Ana', [0]), ('Ana', [0, 0, 0]), ('Ana', [-1, 0]), ('Ana', [3, 0]), ('Ana', [0, 2]), ('Ana', [True, 0]), ('Ana', ['1', 0])]:
            with self.subTest(name=name, answers=answers):
                self.assertEqual(self.client.post(f'/polls/{poll_id}/vote', json={'name': name, 'answers': answers}).status_code, 422)
        self.assertEqual(self.client.post(f'/polls/{poll_id}/vote', json={'name': 'Ana Novak', 'answers': [0, 0]}).status_code, 201)
        self.assertEqual(self.client.post(f'/polls/{poll_id}/vote', json={'name': '  ANA   Novak ', 'answers': [1, 1]}).status_code, 409)

    def test_admin_validation_and_permissions(self):
        self.assertEqual(self.client.get('/admin/polls').status_code, 401)
        self.assertEqual(self.client.post('/admin/polls', json=self.body).status_code, 401)
        for body in [{'title': ' ', 'questions': self.body['questions']}, {'title': 'Test', 'questions': []}, {'title': 'Test', 'questions': [{'text': ' ', 'options': ['a', 'b']}]}, {'title': 'Test', 'questions': [{'text': 'Test', 'options': ['a']}]}, {'title': 'Test', 'questions': [{'text': 'Test', 'options': ['a', ' A ']}]}, {'title': 'Test', 'questions': [{'text': 'Test', 'options': ['a', ' ']}]}]:
            self.assertEqual(self.client.post('/admin/polls', headers=self.admin, json=body).status_code, 422)
        poll_id = self.create()
        self.assertEqual(self.client.post(f'/admin/polls/{poll_id}/archive').status_code, 401)
        self.assertEqual(self.client.post('/admin/polls/999999/archive', headers=self.admin).status_code, 404)
        another = self.create()
        vote = self.client.post(f'/polls/{poll_id}/vote', json={'name': 'Test', 'answers': [0, 0]}).json()
        self.assertEqual(self.client.get(f'/polls/{another}/results', headers={'X-Poll-Token': vote['token']}).status_code, 403)


    def test_existing_database_upgrade_keeps_events_and_responses(self):
        import tempfile
        from pathlib import Path
        from sqlalchemy import create_engine, text, inspect
        from app.main import Base, Event, Response
        with tempfile.TemporaryDirectory() as directory:
            legacy = create_engine(f"sqlite:///{Path(directory) / 'legacy.db'}")
            Event.__table__.create(legacy)
            Response.__table__.create(legacy)
            with legacy.begin() as connection:
                connection.execute(Event.__table__.insert().values(id=1, date='2026-10-20', start_time='19:00', location='Dvorana', minimum_players=6, active=True))
                connection.execute(Response.__table__.insert().values(id=1, event_id=1, name='Obstoječi udeleženec', response='playing', client_token='existing-token'))
            Base.metadata.create_all(legacy)
            self.assertEqual(set(inspect(legacy).get_table_names()), {'events', 'responses', 'polls', 'poll_submissions'})
            with legacy.connect() as connection:
                self.assertEqual(connection.execute(text('SELECT name, client_token FROM responses')).one(), ('Obstoječi udeleženec', 'existing-token'))
                self.assertEqual(connection.execute(text('SELECT location FROM events')).scalar(), 'Dvorana')
            legacy.dispose()


if __name__ == '__main__':
    unittest.main()
