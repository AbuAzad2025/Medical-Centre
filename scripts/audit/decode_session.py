import os

from dotenv import load_dotenv
from flask.sessions import TaggedJSONSerializer
from itsdangerous import URLSafeTimedSerializer

load_dotenv()
secret = os.environ['SECRET_KEY']
serializer = URLSafeTimedSerializer(
    secret, salt='cookie-session', serializer=TaggedJSONSerializer()
)
value = os.environ.get('SESSION_COOKIE', '')
if value:
    print(serializer.loads(value))
else:
    print('set SESSION_COOKIE env')
