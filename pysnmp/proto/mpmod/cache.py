#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof deceased
#
"""State a message processing model keeps between a request and its response."""

from pysnmp import nextid
from pysnmp.proto import error


class Cache:
    """Holds what a message processing model needs when the response arrives.

    Indexed two ways: by the message ID that goes on the wire, and by the state
    reference the engine passes around internally.
    """

    __stateReference = nextid.Integer(0xFFFFFF)
    __msgID = nextid.Integer(0xFFFFFF)

    def __init__(self):
        """Three indices over the same entries, plus the expiration queue.

        A message is looked up by the message ID that came back on the wire, by the
        state reference the engine passes internally, and by the handle the application
        holds -- three different questions about one exchange. The expiration queue is
        what eventually drops an exchange nothing answered.
        """
        self.__msgIdIndex = {}
        self.__stateReferenceIndex = {}
        self.__sendPduHandleIdx = {}
        # Message expiration mechanics
        self.__expirationQueue = {}
        self.__expirationTimer = 0

    # Server mode cache handling

    def newStateReference(self):
        """A fresh handle for a request being served, for the agent side."""
        return self.__stateReference()

    def pushByStateRef(self, stateReference, **msgInfo):
        """Remember what answering a request will need, under its state reference.

        A duplicate reference is a bug rather than a race, so it raises. The entry is
        put on the expiry queue at the same time -- 600 ticks out -- because an
        application that never answers must not hold the entry forever.
        """
        if stateReference in self.__stateReferenceIndex:
            raise error.ProtocolError(
                f"Cache dup for stateReference={stateReference} at {self}"
            )
        expireAt = self.__expirationTimer + 600
        self.__stateReferenceIndex[stateReference] = msgInfo, expireAt

        # Schedule to expire
        if expireAt not in self.__expirationQueue:
            self.__expirationQueue[expireAt] = {}
        if "stateReference" not in self.__expirationQueue[expireAt]:
            self.__expirationQueue[expireAt]["stateReference"] = {}
        self.__expirationQueue[expireAt]["stateReference"][stateReference] = 1

    def popByStateRef(self, stateReference):
        """Take back what was remembered for a request being served.

        A miss raises: the engine only asks for a reference it was given, so a missing
        one means the request was already answered or has expired, and either way the
        response being built has nowhere to go.
        """
        if stateReference in self.__stateReferenceIndex:
            cacheInfo = self.__stateReferenceIndex[stateReference]
        else:
            raise error.ProtocolError(
                f"Cache miss for stateReference={stateReference} at {self}"
            )
        del self.__stateReferenceIndex[stateReference]
        cacheEntry, expireAt = cacheInfo
        del self.__expirationQueue[expireAt]["stateReference"][stateReference]
        return cacheEntry

    # Client mode cache handling

    def newMsgID(self):
        """A fresh message ID for a request being sent, for the manager side."""
        return self.__msgID()

    def pushByMsgId(self, msgId, **msgInfo):
        """Remember a request under its message ID, and under its PDU handle too.

        Two indices because the two directions ask differently: a response arrives
        naming the message ID, while the application cancels or times out naming the
        handle it was given.
        """
        if msgId in self.__msgIdIndex:
            raise error.ProtocolError(f"Cache dup for msgId={msgId} at {self}")
        expireAt = self.__expirationTimer + 600
        self.__msgIdIndex[msgId] = msgInfo, expireAt

        self.__sendPduHandleIdx[msgInfo["sendPduHandle"]] = msgId

        # Schedule to expire
        if expireAt not in self.__expirationQueue:
            self.__expirationQueue[expireAt] = {}
        if "msgId" not in self.__expirationQueue[expireAt]:
            self.__expirationQueue[expireAt]["msgId"] = {}
        self.__expirationQueue[expireAt]["msgId"][msgId] = 1

    def popByMsgId(self, msgId):
        """Take back a sent request by the message ID a response quoted."""
        if msgId in self.__msgIdIndex:
            cacheInfo = self.__msgIdIndex[msgId]
        else:
            raise error.ProtocolError(f"Cache miss for msgId={msgId} at {self}")
        msgInfo, expireAt = cacheInfo
        del self.__sendPduHandleIdx[msgInfo["sendPduHandle"]]
        del self.__msgIdIndex[msgId]
        cacheEntry, expireAt = cacheInfo
        del self.__expirationQueue[expireAt]["msgId"][msgId]
        return cacheEntry

    def popBySendPduHandle(self, sendPduHandle):
        """Take back a sent request by the handle the application holds.

        Unlike the message-ID path a miss is silent, since the application may release
        a request that has already been answered or expired.
        """
        if sendPduHandle in self.__sendPduHandleIdx:
            self.popByMsgId(self.__sendPduHandleIdx[sendPduHandle])

    def expireCaches(self):
        # Uses internal clock to expire pending messages
        """Drop everything scheduled to expire on this tick, and advance the clock.

        The clock is the number of timer ticks, not wall time, so expiry follows the
        dispatcher's timer rather than the system clock -- which is what keeps it
        stable across a clock step.
        """
        if self.__expirationTimer in self.__expirationQueue:
            cacheInfo = self.__expirationQueue[self.__expirationTimer]
            if "stateReference" in cacheInfo:
                for stateReference in cacheInfo["stateReference"]:
                    del self.__stateReferenceIndex[stateReference]
            if "msgId" in cacheInfo:
                for msgId in cacheInfo["msgId"]:
                    del self.__msgIdIndex[msgId]
            del self.__expirationQueue[self.__expirationTimer]
        self.__expirationTimer += 1
