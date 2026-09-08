from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from adaptive_platform.agents import m4_agent_profiles
from adaptive_platform.api.dependencies import get_session
from adaptive_platform.api.schemas import (
    AbstentionReviewItem,
    AgentProfileResponse,
    ClaimEvidenceResponse,
    GroundedClaimResponse,
    HumanFeedbackCreate,
    QuestionResponse,
    ReviewQueueResponse,
    TraceEventResponse,
    UnresolvedReferenceReviewItem,
)
from adaptive_platform.database.models import (
    QuestionTaskRecord,
    RelationshipRecord,
    RepositoryFileRecord,
    TraceEventRecord,
)
from adaptive_platform.qa import QuestionService
from adaptive_platform.services import ServiceError

router = APIRouter(tags=["tasks"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def question_response(session: Session, task: QuestionTaskRecord) -> QuestionResponse:
    answer = task.answer
    claims: list[GroundedClaimResponse] = []
    if answer is not None:
        for claim in sorted(answer.claims, key=lambda item: item.position):
            evidence = []
            for link in claim.evidence_links:
                file_path = None
                if link.file_id is not None:
                    file = session.get(RepositoryFileRecord, link.file_id)
                    file_path = file.path if file is not None else None
                evidence.append(
                    ClaimEvidenceResponse(
                        ref_type=link.ref_type,
                        evidence_ref=link.evidence_ref,
                        path=file_path,
                        start_line=link.start_line,
                        end_line=link.end_line,
                        evidence_type=link.evidence_type,
                        provenance=link.provenance,
                    )
                )
            claims.append(
                GroundedClaimResponse(
                    text=claim.text,
                    claim_type=claim.claim_type,
                    importance=claim.importance,
                    verdict=claim.verdict,
                    evidence=evidence,
                )
            )
    return QuestionResponse(
        task_id=task.id,
        repository_id=task.repository_id,
        scan_id=task.scan_id,
        question=task.question,
        query_class=task.query_class,
        query_intent=task.query_intent,
        status=task.status,
        answer=answer.answer_text if answer is not None else None,
        confidence=answer.confidence if answer is not None else "NONE",
        context_hash=task.context_hash,
        claims=claims,
        gaps=list(answer.gaps) if answer is not None else [],
        cache_status=task.cache_status,
        trace_url=f"/tasks/{task.id}/trace",
    )


def trace_response(event: TraceEventRecord) -> TraceEventResponse:
    return TraceEventResponse(
        id=event.id,
        task_id=event.task_id,
        repository_id=event.repository_id,
        scan_id=event.scan_id,
        correlation_id=event.correlation_id,
        correction_of=event.correction_of,
        category=event.category,
        event_type=event.event_type,
        actor_type=event.actor_type,
        occurred_at=event.occurred_at,
        summary=event.summary,
        rationale_summary=event.rationale_summary,
        input_refs=list(event.input_refs),
        output_refs=list(event.output_refs),
        metadata=dict(event.event_metadata),
    )


@router.get("/tasks/{task_id}", response_model=QuestionResponse)
def get_task(task_id: UUID, session: DatabaseSession) -> QuestionResponse:
    task = QuestionService(session).get(task_id)
    return question_response(session, task)


@router.get("/tasks/{task_id}/trace", response_model=list[TraceEventResponse])
def get_task_trace(
    task_id: UUID, session: DatabaseSession
) -> list[TraceEventResponse]:
    return [trace_response(event) for event in QuestionService(session).trace(task_id)]


@router.post("/tasks/{task_id}/feedback", response_model=TraceEventResponse)
def append_task_feedback(
    task_id: UUID,
    body: HumanFeedbackCreate,
    session: DatabaseSession,
) -> TraceEventResponse:
    task = QuestionService(session).get(task_id)
    if body.corrected_event_id is not None:
        corrected = session.scalar(
            select(TraceEventRecord).where(
                TraceEventRecord.id == body.corrected_event_id,
                TraceEventRecord.task_id == str(task_id),
            )
        )
        if corrected is None:
            raise ServiceError(
                "TRACE_EVENT_NOT_FOUND",
                "The corrected event was not found in this task trace",
                404,
            )
    event = TraceEventRecord(
        task_id=str(task.id),
        repository_id=task.repository_id,
        scan_id=task.scan_id,
        correlation_id=str(task.id),
        correction_of=body.corrected_event_id,
        category="HUMAN_FEEDBACK",
        event_type="human_correction_recorded",
        actor_type="HUMAN",
        occurred_at=datetime.now(UTC),
        summary=body.summary,
        rationale_summary=None,
        input_refs=[f"task:{task.id}"],
        output_refs=[],
        event_metadata={
            "author_role": body.author_role,
            "disposition": body.disposition,
            "mutated_prior_answer": False,
        },
    )
    session.add(event)
    session.commit()
    return trace_response(event)


@router.get("/agent-profiles", response_model=list[AgentProfileResponse])
def list_agent_profiles() -> list[AgentProfileResponse]:
    return [
        AgentProfileResponse(
            profile_id=profile.profile_id,
            version=profile.version,
            role=profile.role.value,
            status=profile.status.value,
            input_schema=profile.input_schema,
            output_schema=profile.output_schema,
            required_payload_keys=list(profile.required_payload_keys),
            permissions=[permission.value for permission in profile.permissions],
            required_gates=list(profile.required_gates),
            max_model_calls=profile.max_model_calls,
            direct_repository_access=profile.direct_repository_access,
            command_access=profile.command_access,
            source_write_access=profile.source_write_access,
            secret_access=profile.secret_access,
            network_access=profile.network_access,
            external_side_effect_access=profile.external_side_effect_access,
            approval_authority=profile.approval_authority,
            profile_hash=profile.profile_hash,
        )
        for profile in m4_agent_profiles()
    ]


@router.get("/review", response_model=ReviewQueueResponse)
def get_review_queues(session: DatabaseSession) -> ReviewQueueResponse:
    abstained = list(
        session.scalars(
            select(QuestionTaskRecord)
            .where(QuestionTaskRecord.status == "ABSTAINED")
            .order_by(QuestionTaskRecord.created_at, QuestionTaskRecord.id)
        )
    )
    unresolved = list(
        session.scalars(
            select(RelationshipRecord)
            .where(RelationshipRecord.resolution_status == "UNRESOLVED")
            .order_by(
                RelationshipRecord.scan_id,
                RelationshipRecord.evidence_file_id,
                RelationshipRecord.evidence_start_line,
                RelationshipRecord.id,
            )
        )
    )
    return ReviewQueueResponse(
        abstentions=[
            AbstentionReviewItem(
                task_id=task.id,
                repository_id=task.repository_id,
                scan_id=task.scan_id,
                question=task.question,
                gaps=list(task.answer.gaps) if task.answer is not None else [],
                created_at=task.created_at,
            )
            for task in abstained
        ],
        unresolved_references=[
            UnresolvedReferenceReviewItem(
                relationship_id=item.id,
                scan_id=item.scan_id,
                unresolved_target=item.unresolved_target or "",
                resolution_reason=item.resolution_reason,
                evidence_file_id=item.evidence_file_id,
                start_line=item.evidence_start_line,
                end_line=item.evidence_end_line,
            )
            for item in unresolved
        ],
        candidate_rules_status="DISABLED_UNTIL_V0.4",
    )
