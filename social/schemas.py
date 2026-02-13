from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal
from datetime import datetime



class UserMiniOut(BaseModel):
    id: str
    username: str
    displayName: str
    avatarUrl: Optional[str] = None
    rating: int = 1200



FriendStatus = Literal["none", "incoming", "outgoing", "friends"]
FriendRequestStatus = Literal["PENDING", "ACCEPTED", "REJECTED", "DECLINED"]


class FriendStatusData(BaseModel):
    userId: str
    status: FriendStatus


class FriendStatusResponse(BaseModel):
    success: bool = True
    data: FriendStatusData



class SearchUserOut(UserMiniOut):
    friendStatus: FriendStatus = "none"


class SearchUsersResponse(BaseModel):
    success: bool = True
    data: List[SearchUserOut]
    pagination: Dict[str, int]



class FriendRequestOut(BaseModel):
    id: str
    status: FriendRequestStatus
    createdAt: datetime
    requester: Optional[UserMiniOut] = None
    addressee: Optional[UserMiniOut] = None


class FriendRequestsResponse(BaseModel):
    success: bool = True
    data: List[FriendRequestOut]


class FriendsListResponse(BaseModel):
    success: bool = True
    data: List[UserMiniOut]


class BasicMessageResponse(BaseModel):
    success: bool = True
    message: str


class SendFriendRequestResponse(BaseModel):
    success: bool = True
    message: str
    requestId: Optional[str] = None



class SendMessageRequest(BaseModel):
    toUserId: str
    content: str = Field(..., min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: str
    conversationId: str
    senderId: str
    recipientId: str
    content: str
    createdAt: datetime
    readAt: Optional[datetime] = None


class ConversationOut(BaseModel):
    id: str
    otherUser: UserMiniOut
    lastMessage: Optional[str] = None
    lastMessageAt: Optional[datetime] = None
    unreadCount: int = 0


class ConversationsResponse(BaseModel):
    success: bool = True
    data: List[ConversationOut]


class MessagesResponse(BaseModel):
    success: bool = True
    data: List[MessageOut]
    pagination: dict


class ChatSettingsData(BaseModel):
    allowNonFriendMessages: bool


class ChatSettingsResponse(BaseModel):
    success: bool = True
    data: ChatSettingsData


class UpdateChatSettingsRequest(BaseModel):
    allowNonFriendMessages: bool
