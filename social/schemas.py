from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UserMiniOut(BaseModel):
    id: str
    username: str
    displayName: str
    avatarUrl: Optional[str] = None
    rating: int = 1200


class SearchUsersResponse(BaseModel):
    success: bool = True
    data: List[UserMiniOut]
    pagination: dict


class FriendRequestOut(BaseModel):
    id: str
    status: str
    createdAt: datetime
    requester: UserMiniOut
    addressee: UserMiniOut


class FriendsListResponse(BaseModel):
    success: bool = True
    data: List[UserMiniOut]


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
