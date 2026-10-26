from copy import deepcopy


class FakeAgent:
    def __init__(self, name, replies):
        self.name = name
        self.replies = list(replies)
        self.calls = []

    def run(self, *, prompt, cwd, mode, schema):
        self.calls.append(dict(prompt=prompt, cwd=cwd, mode=mode, schema=schema))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return deepcopy(reply)


def position(marker="independent"):
    return dict(position=marker, recommendation="Use a state machine",
                arguments=["Fixed state space"], assumptions=["Bounded workflow"],
                risks=["Future growth"], change_my_mind=["Dynamic graph required"])


def challenge(identifier):
    return dict(challenges=[dict(id=identifier, claim="Persistence is missing",
                                evidence="No checkpoint is specified", impact="Recovery",
                                question="How is recovery implemented?")])


def rebuttal(identifier):
    return dict(responses=[dict(challenge_id=identifier, decision="PARTIALLY_ACCEPT",
                               reason="Persist transitions", updated_position="SQLite")])


def final(recommendation="Use a state machine", key="state-machine"):
    return dict(decision_key=key, recommendation=recommendation,
                strongest_argument="Bounded workflow", remaining_risk="Future growth",
                confidence=0.8, agreements=["Persistence is necessary"],
                disagreements=[], open_questions=["Expected scale?"])
