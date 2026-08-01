from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation_message import (
    ConversationMessage,
)
from app.database.models.conversation_session import (
    ConversationSession,
)
from app.database.models.conversation_session_metric import (
    ConversationSessionMetric,
)
from app.database.models.conversation_tool_execution import (
    ConversationToolExecution,
)
from app.features.conversation_logs.exceptions import (
    ConversationLogMetricsNotFoundError,
    ConversationLogNotFoundError,
    InvalidConversationLogDateRangeError,
    InvalidConversationLogSessionIdError,
    OrganizationNotFoundError,
)
from app.features.conversation_logs.repository import (
    ConversationLogRepository,
)
from app.features.conversation_logs.schemas import (
    ConversationAnalyticsMessageTotalsResponse,
    ConversationAnalyticsPerformanceResponse,
    ConversationAnalyticsSessionCountsResponse,
    ConversationAnalyticsSummaryResponse,
    ConversationAnalyticsTokenTotalsResponse,
    ConversationAnalyticsToolTotalsResponse,
    ConversationAnalyticsToolUsageResponse,
    ConversationLogDetailResponse,
    ConversationLogListResponse,
    ConversationLogMessageResponse,
    ConversationLogMetricsResponse,
    ConversationLogSessionResponse,
    ConversationLogSummaryResponse,
    ConversationLogToolExecutionResponse,
    ConversationSessionStatus,
)
from app.features.organizations.repository import (
    OrganizationRepository,
)


class ConversationLogService:
    """Read and assemble organization-scoped conversation logs."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._repository = ConversationLogRepository(
            session
        )

        self._organizations = OrganizationRepository(
            session
        )

    async def list_conversations(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ) = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> ConversationLogListResponse:
        """
        Return paginated conversation summaries for an organization.

        Historical records remain available when an organization is
        inactive.
        """

        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        self._validate_date_range(
            started_from=started_from,
            started_to=started_to,
        )

        await self._require_organization(
            organization_id=organization_id,
        )

        total = await self._repository.count_by_organization(
            organization_id=organization_id,
            conversation_status=conversation_status,
            started_from=started_from,
            started_to=started_to,
        )

        rows = await self._repository.list_by_organization(
            organization_id=organization_id,
            conversation_status=conversation_status,
            started_from=started_from,
            started_to=started_to,
            limit=limit,
            offset=offset,
        )

        items: list[
            ConversationLogSummaryResponse
        ] = []

        for (
            conversation_session,
            metrics,
        ) in rows:
            required_metrics = self._require_metrics(
                conversation_session=conversation_session,
                metrics=metrics,
            )

            items.append(
                self._map_summary(
                    conversation_session=conversation_session,
                    metrics=required_metrics,
                )
            )

        return ConversationLogListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_conversation(
        self,
        *,
        organization_id: int,
        public_id: str,
    ) -> ConversationLogDetailResponse:
        """
        Return one complete organization-scoped conversation log.

        Reading the log does not renew, close, refresh, or otherwise
        mutate the conversation.
        """

        await self._require_organization(
            organization_id=organization_id,
        )

        normalized_public_id = self._normalize_public_id(
            public_id
        )

        detail_row = await self._repository.get_by_public_id(
            organization_id=organization_id,
            public_id=normalized_public_id,
        )

        if detail_row is None:
            raise ConversationLogNotFoundError()

        (
            conversation_session,
            metrics,
        ) = detail_row

        required_metrics = self._require_metrics(
            conversation_session=conversation_session,
            metrics=metrics,
        )

        messages = (
            await self._repository.list_messages_by_session(
                session_id=conversation_session.id,
            )
        )

        tool_executions = (
            await self._repository
            .list_tool_executions_by_session(
                session_id=conversation_session.id,
            )
        )

        executions_by_message_id: dict[
            int,
            list[
                ConversationLogToolExecutionResponse
            ],
        ] = defaultdict(list)

        for execution in tool_executions:
            executions_by_message_id[
                execution.assistant_message_id
            ].append(
                self._map_tool_execution(
                    execution
                )
            )

        message_responses = [
            self._map_message(
                message=message,
                tool_executions=(
                    executions_by_message_id.get(
                        message.id,
                        [],
                    )
                ),
            )
            for message in messages
        ]

        return ConversationLogDetailResponse(
            session=self._map_session(
                conversation_session
            ),
            metrics=self._map_metrics(
                required_metrics
            ),
            messages=message_responses,
        )



    async def get_analytics_summary(
        self,
        *,
        organization_id: int,
        conversation_status: (
            ConversationSessionStatus | None
        ) = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
    ) -> ConversationAnalyticsSummaryResponse:
        """
        Return organization-wide conversation analytics.

        All aggregates use the same organization, session-status, and
        session-start date boundaries. This operation is read-only.
        """

        self._validate_date_range(
            started_from=started_from,
            started_to=started_to,
        )

        await self._require_organization(
            organization_id=organization_id,
        )

        session_counts = (
            await self._repository
            .get_analytics_session_counts(
                organization_id=organization_id,
                conversation_status=conversation_status,
                started_from=started_from,
                started_to=started_to,
            )
        )

        metric_totals = (
            await self._repository
            .get_analytics_metric_totals(
                organization_id=organization_id,
                conversation_status=conversation_status,
                started_from=started_from,
                started_to=started_to,
            )
        )

        performance = (
            await self._repository
            .get_analytics_performance(
                organization_id=organization_id,
                conversation_status=conversation_status,
                started_from=started_from,
                started_to=started_to,
            )
        )

        tool_usage_rows = (
            await self._repository
            .list_analytics_tool_usage(
                organization_id=organization_id,
                conversation_status=conversation_status,
                started_from=started_from,
                started_to=started_to,
            )
        )

        tool_usage = [
            ConversationAnalyticsToolUsageResponse(
                tool_name=row.tool_name,
                execution_count=row.execution_count,
                succeeded_count=row.succeeded_count,
                execution_failed_count=(
                    row.execution_failed_count
                ),
                arguments_rejected_count=(
                    row.arguments_rejected_count
                ),
                unknown_tool_count=(
                    row.unknown_tool_count
                ),
                success_rate_percent=(
                    self._calculate_percentage(
                        numerator=row.succeeded_count,
                        denominator=row.execution_count,
                    )
                ),
                average_duration_ms=(
                    self._round_optional_float(
                        row.average_duration_ms
                    )
                ),
                maximum_duration_ms=(
                    row.maximum_duration_ms
                ),
            )
            for row in tool_usage_rows
        ]

        tool_call_count = sum(
            item.execution_count
            for item in tool_usage
        )

        successful_tool_call_count = sum(
            item.succeeded_count
            for item in tool_usage
        )

        failed_tool_call_count = max(
            0,
            (
                tool_call_count
                - successful_tool_call_count
            ),
        )

        user_message_count = (
            metric_totals.user_message_count
        )

        assistant_message_count = (
            metric_totals.assistant_message_count
        )

        total_input_tokens = (
            metric_totals.total_input_tokens
        )

        total_output_tokens = (
            metric_totals.total_output_tokens
        )

        return ConversationAnalyticsSummaryResponse(
            organization_id=organization_id,
            status_filter=conversation_status,
            started_from=started_from,
            started_to=started_to,
            sessions=(
                ConversationAnalyticsSessionCountsResponse(
                    total=session_counts.total,
                    active=session_counts.active,
                    closed=session_counts.closed,
                    expired=session_counts.expired,
                    abandoned=session_counts.abandoned,
                    error=session_counts.error,
                )
            ),
            messages=(
                ConversationAnalyticsMessageTotalsResponse(
                    total=(
                        user_message_count
                        + assistant_message_count
                    ),
                    user=user_message_count,
                    assistant=assistant_message_count,
                    recorded_error_count=(
                        metric_totals.error_count
                    ),
                )
            ),
            tokens=(
                ConversationAnalyticsTokenTotalsResponse(
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    total_tokens=(
                        total_input_tokens
                        + total_output_tokens
                    ),
                )
            ),
            tools=(
                ConversationAnalyticsToolTotalsResponse(
                    tool_call_count=tool_call_count,
                    successful_tool_call_count=(
                        successful_tool_call_count
                    ),
                    failed_tool_call_count=(
                        failed_tool_call_count
                    ),
                    success_rate_percent=(
                        self._calculate_percentage(
                            numerator=(
                                successful_tool_call_count
                            ),
                            denominator=tool_call_count,
                        )
                    ),
                )
            ),
            performance=(
                ConversationAnalyticsPerformanceResponse(
                    average_duration_seconds=(
                        self._round_optional_float(
                            metric_totals
                            .average_duration_seconds
                        )
                    ),
                    average_total_response_time_ms=(
                        self._round_optional_int(
                            performance
                            .average_total_response_time_ms
                        )
                    ),
                    maximum_total_response_time_ms=(
                        performance
                        .maximum_total_response_time_ms
                    ),
                    average_time_to_first_token_ms=(
                        self._round_optional_int(
                            performance
                            .average_time_to_first_token_ms
                        )
                    ),
                    maximum_time_to_first_token_ms=(
                        performance
                        .maximum_time_to_first_token_ms
                    ),
                    average_model_time_to_first_token_ms=(
                        self._round_optional_int(
                            performance
                            .average_model_time_to_first_token_ms
                        )
                    ),
                )
            ),
            tool_usage=tool_usage,
        )

    async def _require_organization(
        self,
        *,
        organization_id: int,
    ) -> None:
        """
        Verify that the organization exists.

        An active status is intentionally not required because
        administrators must be able to review historical records.
        """

        organization = (
            await self._organizations.get_by_id(
                organization_id=organization_id,
            )
        )

        if organization is None:
            raise OrganizationNotFoundError()

    def _require_metrics(
        self,
        *,
        conversation_session: ConversationSession,
        metrics: ConversationSessionMetric | None,
    ) -> ConversationSessionMetric:
        """Return required metrics or report inconsistent stored data."""

        if metrics is None:
            raise ConversationLogMetricsNotFoundError(
                public_id=conversation_session.public_id,
            )

        return metrics

    def _normalize_public_id(
        self,
        public_id: str,
    ) -> str:
        """Validate and normalize a public conversation UUID."""

        try:
            parsed_id = UUID(
                public_id.strip()
            )
        except (
            AttributeError,
            ValueError,
        ) as error:
            raise (
                InvalidConversationLogSessionIdError()
            ) from error

        return str(
            parsed_id
        )

    def _validate_pagination(
        self,
        *,
        limit: int,
        offset: int,
    ) -> None:
        """Validate service-level pagination boundaries."""

        if limit < 1 or limit > 100:
            raise ValueError(
                "limit must be between 1 and 100"
            )

        if offset < 0:
            raise ValueError(
                "offset must be zero or greater"
            )

    def _validate_date_range(
        self,
        *,
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> None:
        """Validate the optional conversation start-date range."""

        if (
            started_from is not None
            and started_to is not None
            and started_to < started_from
        ):
            raise InvalidConversationLogDateRangeError()


    def _calculate_percentage(
        self,
        *,
        numerator: int,
        denominator: int,
    ) -> float | None:
        """Return a percentage rounded to two decimal places."""

        if denominator == 0:
            return None

        return round(
            (
                numerator
                / denominator
            )
            * 100,
            2,
        )

    def _round_optional_float(
        self,
        value: float | None,
    ) -> float | None:
        """Round an optional floating-point average."""

        if value is None:
            return None

        return round(
            value,
            2,
        )

    def _round_optional_int(
        self,
        value: float | None,
    ) -> int | None:
        """Round an optional numeric average to a whole unit."""

        if value is None:
            return None

        return round(
            value
        )

    def _map_session(
        self,
        conversation_session: ConversationSession,
    ) -> ConversationLogSessionResponse:
        """Map a stored session into its public response contract."""

        return ConversationLogSessionResponse(
            session_id=conversation_session.public_id,
            organization_id=(
                conversation_session.organization_id
            ),
            status=conversation_session.status,
            channel=conversation_session.channel,
            model_profile_key=(
                conversation_session.model_profile_key
            ),
            started_at=conversation_session.started_at,
            last_activity_at=(
                conversation_session.last_activity_at
            ),
            expires_at=conversation_session.expires_at,
            ended_at=conversation_session.ended_at,
            close_reason=(
                conversation_session.close_reason
            ),
            created_at=conversation_session.created_at,
            updated_at=conversation_session.updated_at,
        )

    def _map_metrics(
        self,
        metrics: ConversationSessionMetric,
    ) -> ConversationLogMetricsResponse:
        """Map stored metrics into their public response contract."""

        return ConversationLogMetricsResponse(
            user_message_count=metrics.user_message_count,
            assistant_message_count=(
                metrics.assistant_message_count
            ),
            tool_call_count=metrics.tool_call_count,
            successful_tool_call_count=(
                metrics.successful_tool_call_count
            ),
            failed_tool_call_count=(
                metrics.failed_tool_call_count
            ),
            error_count=metrics.error_count,
            duration_seconds=metrics.duration_seconds,
            average_time_to_first_token_ms=(
                metrics.average_time_to_first_token_ms
            ),
            maximum_time_to_first_token_ms=(
                metrics.maximum_time_to_first_token_ms
            ),
            average_model_time_to_first_token_ms=(
                metrics
                .average_model_time_to_first_token_ms
            ),
            average_total_response_time_ms=(
                metrics.average_total_response_time_ms
            ),
            maximum_total_response_time_ms=(
                metrics.maximum_total_response_time_ms
            ),
            total_input_tokens=metrics.total_input_tokens,
            total_output_tokens=metrics.total_output_tokens,
            completion_status=metrics.completion_status,
            created_at=metrics.created_at,
            updated_at=metrics.updated_at,
        )

    def _map_summary(
        self,
        *,
        conversation_session: ConversationSession,
        metrics: ConversationSessionMetric,
    ) -> ConversationLogSummaryResponse:
        """Map one session and its metrics into a list row."""

        return ConversationLogSummaryResponse(
            session_id=conversation_session.public_id,
            organization_id=(
                conversation_session.organization_id
            ),
            status=conversation_session.status,
            channel=conversation_session.channel,
            model_profile_key=(
                conversation_session.model_profile_key
            ),
            started_at=conversation_session.started_at,
            last_activity_at=(
                conversation_session.last_activity_at
            ),
            expires_at=conversation_session.expires_at,
            ended_at=conversation_session.ended_at,
            close_reason=(
                conversation_session.close_reason
            ),
            message_count=(
                metrics.user_message_count
                + metrics.assistant_message_count
            ),
            user_message_count=metrics.user_message_count,
            assistant_message_count=(
                metrics.assistant_message_count
            ),
            tool_call_count=metrics.tool_call_count,
            successful_tool_call_count=(
                metrics.successful_tool_call_count
            ),
            failed_tool_call_count=(
                metrics.failed_tool_call_count
            ),
            error_count=metrics.error_count,
            duration_seconds=metrics.duration_seconds,
            average_total_response_time_ms=(
                metrics.average_total_response_time_ms
            ),
            maximum_total_response_time_ms=(
                metrics.maximum_total_response_time_ms
            ),
            total_input_tokens=metrics.total_input_tokens,
            total_output_tokens=metrics.total_output_tokens,
            completion_status=metrics.completion_status,
        )

    def _map_message(
        self,
        *,
        message: ConversationMessage,
        tool_executions: list[
            ConversationLogToolExecutionResponse
        ],
    ) -> ConversationLogMessageResponse:
        """Map one stored message and its associated tool audits."""

        return ConversationLogMessageResponse(
            message_id=message.id,
            sequence_number=message.sequence_number,
            role=message.role,
            message_type=message.message_type,
            status=message.status,
            content=message.content,
            tool_name=message.tool_name,
            tool_arguments=(
                dict(
                    message.tool_arguments_json
                )
                if message.tool_arguments_json is not None
                else None
            ),
            tool_result=(
                dict(
                    message.tool_result_json
                )
                if message.tool_result_json is not None
                else None
            ),
            provider_name=message.provider_name,
            model_name=message.model_name,
            input_tokens=message.input_tokens,
            output_tokens=message.output_tokens,
            tool_call_count=message.tool_call_count,
            successful_tool_call_count=(
                message.successful_tool_call_count
            ),
            request_started_at=(
                message.request_started_at
            ),
            model_started_at=message.model_started_at,
            first_token_at=message.first_token_at,
            completed_at=message.completed_at,
            time_to_first_token_ms=(
                message.time_to_first_token_ms
            ),
            model_time_to_first_token_ms=(
                message.model_time_to_first_token_ms
            ),
            total_response_time_ms=(
                message.total_response_time_ms
            ),
            is_user_visible=message.is_user_visible,
            created_at=message.created_at,
            updated_at=message.updated_at,
            tool_executions=tool_executions,
        )

    def _map_tool_execution(
        self,
        execution: ConversationToolExecution,
    ) -> ConversationLogToolExecutionResponse:
        """Map one audited tool execution into its response contract."""

        return ConversationLogToolExecutionResponse(
            execution_order=execution.execution_order,
            attempt_phase=execution.attempt_phase,
            tool_name=execution.tool_name,
            validated_arguments=(
                execution.validated_arguments_json
            ),
            status=execution.status,
            failure_category=execution.failure_category,
            duration_ms=execution.duration_ms,
            created_at=execution.created_at,
        )