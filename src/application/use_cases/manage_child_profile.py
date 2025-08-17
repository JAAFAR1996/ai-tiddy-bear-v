from typing import Any
from uuid import UUID

from src.shared.dto.child_data import ChildData
from src.core.entities import Child
from src.interfaces.repositories import IChildRepository
from src.interfaces.services import IEventBusService
from src.interfaces.read_model_interfaces import IChildProfileReadModel


class ManageChildProfileUseCase:
    def __init__(
        self,
        child_repository: IChildRepository,
        child_profile_read_model: IChildProfileReadModel,
        event_bus: IEventBusService,
    ):
        self.child_repository = child_repository
        self.child_profile_read_model = child_profile_read_model
        self.event_bus = event_bus

    async def create_child_profile(
        self,
        name: str,
        age: int,
        preferences: dict[str, Any],
    ) -> ChildData:
        child = Child.create(name, age, preferences)
        await self.child_repository.save(child)
        for event in child.get_uncommitted_events():
            await self.event_bus.publish(event)
        return ChildData(
            id=child.id,
            name=child.name,
            age=child.age,
            preferences=child.preferences,
        )

    async def get_child_profile(self, child_id: UUID) -> ChildData | None:
        child_read_model = self.child_profile_read_model_store.get_by_id(child_id)
        if child_read_model:
            return ChildData(
                id=child_read_model.id,
                name=child_read_model.name,
                age=child_read_model.age,
                preferences=child_read_model.preferences,
            )
        return None

    async def update_child_profile(
        self,
        child_id: UUID,
        name: str | None = None,
        age: int | None = None,
        preferences: dict[str, Any] | None = None,
    ) -> ChildData | None:
        child = await self.child_repository.get_by_id(
            child_id,
        )  # Use write model for update
        if child:
            child.update_profile(name, age, preferences)
            await self.child_repository.save(child)
            for event in child.get_uncommitted_events():
                await self.event_bus.publish(event)
            # Retrieve from read model after update for consistency
            return await self.get_child_profile(child_id)
        return None

    async def delete_child_profile(self, child_id: UUID) -> bool:
        child = await self.child_repository.get_by_id(child_id)
        if child:
            await self.child_repository.delete(child_id)
            # In a full event-sourced system, a ChildDeleted event would be published here
            # and the read model would handle the deletion.
            self.child_profile_read_model_store.delete(child_id)
            return True
        return False
