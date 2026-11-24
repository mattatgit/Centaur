"""Resolve historical chat authors from authenticated project membership records."""


def message_profile(message,people,viewer,own_memberships,name):
    identity=message.get('participant')
    if isinstance(identity,str) and identity:
        for person in people:
            if (identity==person.get('id') or identity in person.get('previousIds',[]) or
                    person.get('profileId') and message.get('profileId')==person['profileId']):
                return dict(person,self=person.get('id')==viewer)
        if identity in own_memberships:
            return {'self':True,'displayName':name}
        if identity.startswith('local:'):
            host=next((p for p in people if p.get('id')=='host' and p.get('name')==identity[6:]),None)
            if host: return dict(host,self=viewer=='host')
        return {'self':bool(viewer and viewer==identity)}
    # Name-only entries in a shared history cannot prove who posted them.
    return {'self':False}
