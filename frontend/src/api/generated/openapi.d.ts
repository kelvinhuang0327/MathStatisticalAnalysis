// Generated from contracts/openapi.json. Do not edit by hand.
// OpenAPI 3.1.0; LottoLab API 0.1.0

export interface paths {
  "/api/health": {
      get: {
          parameters: Record<string, never>
          responses: {
                  200: {
                          content: {
                                    "application/json": Record<string, string>
                                  }
                        }
                }
        }
    }
  "/api/v1/strategies": {
      get: {
          parameters: Record<string, never>
          responses: {
                  200: {
                          content: {
                                    "application/json": Array<components['schemas']["StrategyView"]>
                                  }
                        }
                }
        }
    }
  "/api/v1/strategy-overview": {
      get: {
          parameters: {
            "query": {
              "q"?: string | null
              "lottery_type"?: components['schemas']["LotteryType"] | null
              "lifecycle_status"?: components['schemas']["LifecycleStatus"] | null
              "executable"?: boolean | null
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["StrategyOverviewResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/draw-imports/preview": {
      post: {
          parameters: Record<string, never>
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["DrawImportPreviewResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/draw-imports/commit": {
      post: {
          parameters: Record<string, never>
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["ImportCommitResultView"]
                                  }
                        }
                  409: {
                          content: {
                                    "application/json": components['schemas']["CommitConflictResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/draws": {
      get: {
          parameters: {
            "query": {
              "lottery_type"?: components['schemas']["LotteryType"] | null
              "draw_number"?: string | null
              "date_from"?: string | null
              "date_to"?: string | null
              "page"?: number
              "page_size"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["DrawHistoryResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/draws/{lottery_type}/{draw_number}": {
      get: {
          parameters: {
            "path": {
              "lottery_type": components['schemas']["LotteryType"]
              "draw_number": string
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["DrawRecordView"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/ingestion-runs": {
      get: {
          parameters: {
            "query": {
              "status"?: components['schemas']["IngestionRunStatus"] | null
              "lottery_type"?: components['schemas']["LotteryType"] | null
              "page"?: number
              "page_size"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["IngestionRunPageResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/ingestion-runs/{run_id}": {
      get: {
          parameters: {
            "path": {
              "run_id": string
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["IngestionRunDetailResponse"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/generate-bet": {
      post: {
          parameters: Record<string, never>
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["GenerateBetResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/live-zone-split-bets": {
      post: {
          parameters: Record<string, never>
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["LiveZoneSplitResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/historical-results/runs": {
      get: {
          parameters: {
            "query": {
              "limit"?: number
              "offset"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalRunPageResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/historical-results/runs/{run_id}/strategies": {
      get: {
          parameters: {
            "path": {
              "run_id": string
            }
            "query": {
              "ticket_count": components['schemas']["TicketCount"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalStrategySummaryListResponse"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/historical-results/runs/{run_id}/replay": {
      get: {
          parameters: {
            "path": {
              "run_id": string
            }
            "query": {
              "strategy_id": string
              "ticket_count": components['schemas']["TicketCount"]
              "m4plus_only"?: boolean
              "limit"?: number
              "offset"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalReplayPageResponse"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/historical-results/portfolios/{portfolio_id}": {
      get: {
          parameters: {
            "path": {
              "portfolio_id": string
            }
            "query": {
              "ticket_count": components['schemas']["TicketCount"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPortfolioView"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/replay-rankings/optimal": {
      get: {
          parameters: {
            "query": {
              "scoring_artifact_sha256": string
              "top_k"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["ReplayPortfolioRankingResponse"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}": {
      get: {
          parameters: {
            "path": {
              "scoring_artifact_payload_sha256": string
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["ReplayScoringRunResponse"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/predictions": {
      get: {
          parameters: {
            "path": {
              "scoring_artifact_payload_sha256": string
            }
            "query": {
              "target_draw"?: string | null
              "strategy_id"?: string | null
              "status"?: string | null
              "tier"?: string | null
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": Array<components['schemas']["ReplayScoredPredictionView"]>
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates": {
      get: {
          parameters: {
            "path": {
              "scoring_artifact_payload_sha256": string
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": Array<components['schemas']["ReplayStrategyAggregateView"]>
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
  "/api/v1/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate": {
      get: {
          parameters: {
            "path": {
              "scoring_artifact_payload_sha256": string
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["ReplayOverallAggregateResponse"]
                                  }
                        }
                  404: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                  422: {
                          content: {
                                    "application/json": components['schemas']["ApiValidationErrorResponse"]
                                  }
                        }
                  503: {
                          content: {
                                    "application/json": components['schemas']["ApiErrorResponse"]
                                  }
                        }
                }
        }
    }
}

export interface components {
  schemas: {
    "ApiErrorResponse": {
          "error_code": string
          "message": string
        }
    "ApiValidationErrorResponse": {
          "error_code": string
          "message": string
          "preview"?: components['schemas']["DrawImportPreviewResponse"] | null
          "fields"?: Array<components['schemas']["RequestValidationIssueView"]>
        }
    "CommitConflictResponse": {
          "error_code": string
          "message": string
          "result": components['schemas']["ImportCommitResultView"] | null
        }
    "ConflictPolicy": "REJECT"
    "DrawHistoryResponse": {
          "records": Array<components['schemas']["DrawRecordView"]>
          "page": number
          "page_size": number
          "total_count": number
          "total_pages": number
          "sort": Array<string>
        }
    "DrawImportCommitRequest": {
          "filename": string
          "csv_text": string
          "expected_sha256": string
          "parser_version": string
          "conflict_policy": components['schemas']["ConflictPolicy"]
        }
    "DrawImportErrorView": {
          "code": string
          "message": string
          "row_number": number | null
          "field": string | null
        }
    "DrawImportPreviewRequest": {
          "filename": string
          "csv_text": string
          "declared_parser_version"?: string | null
        }
    "DrawImportPreviewResponse": {
          "filename": string
          "is_valid": boolean
          "content_sha256": string
          "parser_version": string
          "supported_lottery_types": Array<components['schemas']["LotteryType"]>
          "total_rows": number
          "valid_rows": number
          "blank_rows": number
          "duplicate_rows": number
          "conflict_rows_inside_input": number
          "validation_error_count": number
          "ignored_columns": Array<string>
          "normalized_preview": Array<components['schemas']["NormalizedDrawPreviewView"]>
          "validation_errors": Array<components['schemas']["DrawImportErrorView"]>
          "preview_truncated": boolean
          "errors_truncated": boolean
        }
    "DrawRecordView": {
          "lottery_type": components['schemas']["LotteryType"]
          "draw_number": string
          "draw_date": string
          "main_numbers": Array<number>
          "special_numbers": Array<number>
          "source_name": string | null
          "source_reference": string | null
          "ingestion_run_id": string
          "created_at": string
          "updated_at": string
        }
    "GenerateBetHistoryRow": {
          "draw": string
          "date": string
          "numbers": Array<number>
        }
    "GenerateBetRequest": {
          "strategy_id": string
          "seed": number
          "history": Array<components['schemas']["GenerateBetHistoryRow"]>
        }
    "GenerateBetResponse": {
          "strategy_id": string
          "lottery_type": components['schemas']["LotteryType"]
          "seed": number
          "status": components['schemas']["GenerateOneBetStatus"]
          "numbers": Array<number> | null
          "reason_code": components['schemas']["GenerateOneBetReason"] | null
        }
    "GenerateLiveZoneSplitBetsReason": "INVALID_NUM_BETS" | "MALFORMED_OUTPUT" | "EXECUTION_ERROR"
    "GenerateLiveZoneSplitBetsStatus": "OK" | "INVALID_REQUEST" | "INVALID_OUTPUT" | "EXECUTION_ERROR"
    "GenerateOneBetReason": "REJECTED_BY_STRATEGY" | "INSUFFICIENT_HISTORY" | "UNKNOWN_STRATEGY" | "ADAPTER_NOT_INJECTED" | "UNSUPPORTED_LOTTERY_TYPE" | "INVALID_OUTPUT" | "REPLAY_ERROR"
    "GenerateOneBetStatus": "OK" | "REJECTED" | "INSUFFICIENT_HISTORY" | "STRATEGY_UNAVAILABLE" | "INVALID_OUTPUT" | "REPLAY_ERROR"
    "HistoricalDrawIdentityView": {
          "draw_number": string
          "draw_date": string
          "main_numbers": Array<number>
          "special_numbers": Array<number>
          "draw_sha256": string
        }
    "HistoricalPortfolioView": {
          "portfolio_id": string
          "run_id": string
          "strategy_snapshot_id": string
          "strategy_id": string
          "effective_strategy_id": string
          "strategy_version": string
          "replicate": number
          "constructor_identifier": string
          "source_record_locator": string | null
          "portfolio_sha256": string
          "prefix10_sha256": string
          "prefix15_sha256": string
          "target_draw": components['schemas']["HistoricalDrawIdentityView"]
          "cutoff_draw": components['schemas']["HistoricalDrawIdentityView"]
          "requested_ticket_count": number
          "m4plus": boolean
          "tickets": Array<components['schemas']["HistoricalTicketView"]>
        }
    "HistoricalReplayPageResponse": {
          "run_id": string
          "strategy_id": string
          "ticket_count": number
          "items": Array<components['schemas']["HistoricalPortfolioView"]>
          "total_count": number
          "limit": number
          "offset": number
        }
    "HistoricalRunPageResponse": {
          "items": Array<components['schemas']["HistoricalRunView"]>
          "total_count": number
          "limit": number
          "offset": number
        }
    "HistoricalRunView": {
          "run_id": string
          "import_identity_sha256": string
          "manifest_sha256": string
          "contract_version": string
          "source_kind": string
          "source_repository": string
          "source_commit_oid": string
          "source_artifact_sha256": string
          "dataset_identity": string
          "dataset_sha256": string
          "legacy_run_id": string | null
          "lottery_type": string
          "started_at": string
          "completed_at": string
        }
    "HistoricalStrategySummaryListResponse": {
          "run_id": string
          "ticket_count": number
          "items": Array<components['schemas']["HistoricalStrategySummaryView"]>
        }
    "HistoricalStrategySummaryView": {
          "strategy_snapshot_id": string
          "strategy_id": string
          "effective_strategy_id": string
          "strategy_version": string
          "replicate": number
          "identity_kind": string
          "governance_status": string
          "alias_of_strategy_id": string | null
          "equivalence_group": string | null
          "nested_prefix_supported": boolean
          "ticket_count": number
          "evaluated_draws": number
          "complete_portfolios": number
          "m4plus_hit_count": number
        }
    "HistoricalTicketView": {
          "portfolio_position": number
          "main_numbers": Array<number>
          "special_numbers": Array<number>
          "main_hit_count": number
          "special_hit": boolean
          "ticket_sha256": string
          "legacy_row_id": string | null
          "legacy_storage_bet_index": number | null
        }
    "ImportCommitResultView": {
          "run_id": string | null
          "status": components['schemas']["IngestionRunStatus"]
          "lottery_type": components['schemas']["LotteryType"] | null
          "total_count": number
          "inserted_count": number
          "skipped_count": number
          "conflict_count": number
          "failed_count": number
          "first_draw_number": string | null
          "last_draw_number": string | null
          "completed_at": string
        }
    "IngestionItemDisposition": "INSERTED" | "SKIPPED_DUPLICATE" | "CONFLICT" | "FAILED"
    "IngestionItemView": {
          "source_row_number": number
          "lottery_type": components['schemas']["LotteryType"] | null
          "draw_number": string | null
          "disposition": components['schemas']["IngestionItemDisposition"]
          "normalized_record_hash": string | null
          "message": string | null
        }
    "IngestionOperationType": "DRAW_CSV_IMPORT"
    "IngestionRunDetailResponse": {
          "run": components['schemas']["IngestionRunView"]
          "items": Array<components['schemas']["IngestionItemView"]>
          "item_count": number
          "items_truncated": boolean
        }
    "IngestionRunPageResponse": {
          "records": Array<components['schemas']["IngestionRunView"]>
          "page": number
          "page_size": number
          "total_count": number
          "total_pages": number
          "sort": Array<string>
        }
    "IngestionRunStatus": "RUNNING" | "SUCCESS" | "FAILED"
    "IngestionRunView": {
          "run_id": string
          "operation_type": components['schemas']["IngestionOperationType"]
          "status": components['schemas']["IngestionRunStatus"]
          "lottery_type": components['schemas']["LotteryType"] | null
          "source_filename": string
          "source_sha256": string
          "parser_version": string
          "total_count": number
          "inserted_count": number
          "skipped_count": number
          "conflict_count": number
          "failed_count": number
          "first_draw_number": string | null
          "last_draw_number": string | null
          "started_at": string
          "completed_at": string | null
          "error_summary": string | null
        }
    "LifecycleStatus": "IDEA" | "OBSERVATION" | "ONLINE" | "REJECTED" | "RETIRED"
    "LiveZoneSplitRequest": {
          "num_bets": number
        }
    "LiveZoneSplitResponse": {
          "status": components['schemas']["GenerateLiveZoneSplitBetsStatus"]
          "bets": Array<Array<number>> | null
          "coverage_rate": number | null
          "total_unique_numbers": number | null
          "method": string | null
          "philosophy": string | null
          "reason_code": components['schemas']["GenerateLiveZoneSplitBetsReason"] | null
        }
    "LotteryType": "DAILY_539" | "BIG_LOTTO" | "POWER_LOTTO"
    "NormalizedDrawPreviewView": {
          "source_row_number": number
          "lottery_type": components['schemas']["LotteryType"]
          "draw_number": string
          "draw_date": string
          "main_numbers": Array<number>
          "special_numbers": Array<number>
          "source_reference": string | null
          "normalized_record_hash": string
        }
    "ReplayOverallAggregateResponse": {
          "run_payload_sha256": string
          "source_snapshot_count": number
          "scored_count": number
          "history_closed_count": number
          "prediction_closed_count": number
          "target_outcome_not_found_count": number
          "target_identity_mismatch_count": number
          "first_prize_count": number
          "second_prize_count": number
          "third_prize_count": number
          "fourth_prize_count": number
          "fifth_prize_count": number
          "sixth_prize_count": number
          "seventh_prize_count": number
          "general_prize_count": number
          "no_prize_count": number
          "aggregate_sha256": string
        }
    "ReplayPortfolioRankingCandidateView": {
          "rank": number
          "ticket_count": number
          "members": Array<components['schemas']["ReplayPortfolioRankingMemberView"]>
          "target_count": number
          "total_ticket_count": number
          "scored_count": number
          "history_closed_count": number
          "prediction_closed_count": number
          "target_outcome_not_found_count": number
          "target_identity_mismatch_count": number
          "first_prize_count": number
          "second_prize_count": number
          "third_prize_count": number
          "fourth_prize_count": number
          "fifth_prize_count": number
          "sixth_prize_count": number
          "seventh_prize_count": number
          "general_prize_count": number
          "no_prize_count": number
          "winning_ticket_count": number
          "candidate_sha256": string
        }
    "ReplayPortfolioRankingGroupView": {
          "ticket_count": number
          "status": string
          "total_candidate_count": number
          "candidates": Array<components['schemas']["ReplayPortfolioRankingCandidateView"]>
        }
    "ReplayPortfolioRankingMemberView": {
          "source_position": number
          "strategy_id": string
          "strategy_version"?: string | null
        }
    "ReplayPortfolioRankingResponse": {
          "artifact_schema_version": string
          "ranking_policy_id": string
          "source_scoring_artifact_payload_sha256": string
          "source_replay_artifact_payload_sha256": string
          "dataset_id": string
          "dataset_version": string
          "lottery_type": string
          "target_count": number
          "strategy_count": number
          "top_k": number
          "groups": Array<components['schemas']["ReplayPortfolioRankingGroupView"]>
          "artifact_sha256": string
        }
    "ReplayScoredPredictionView": {
          "run_payload_sha256": string
          "ordinal": number
          "source_snapshot_result_sha256": string
          "scored_result_sha256": string
          "target_draw_number": string
          "target_draw_date": string
          "strategy_id": string
          "strategy_version"?: string | null
          "source_history_status": string
          "source_history_reason_code"?: string | null
          "source_prediction_status"?: string | null
          "source_prediction_reason_code"?: string | null
          "scoring_status": string
          "scoring_reason_code"?: string | null
          "predicted_main_numbers"?: Array<number> | null
          "target_outcome_sha256"?: string | null
          "main_number_hit_count"?: number | null
          "special_number_hit"?: boolean | null
          "prize_tier_id"?: string | null
          "prize_official_label"?: string | null
          "no_prize_result"?: string | null
        }
    "ReplayScoringRunResponse": {
          "scoring_artifact_schema_version": string
          "scoring_artifact_payload_sha256": string
          "source_replay_artifact_payload_sha256": string
          "dataset_id": string
          "dataset_version": string
          "lottery_type": string
          "target_count": number
          "strategy_count": number
          "scored_record_count": number
          "overall_aggregate_sha256": string
        }
    "ReplayStrategyAggregateView": {
          "run_payload_sha256": string
          "ordinal": number
          "strategy_id": string
          "strategy_version"?: string | null
          "source_snapshot_count": number
          "scored_count": number
          "history_closed_count": number
          "prediction_closed_count": number
          "target_outcome_not_found_count": number
          "target_identity_mismatch_count": number
          "first_prize_count": number
          "second_prize_count": number
          "third_prize_count": number
          "fourth_prize_count": number
          "fifth_prize_count": number
          "sixth_prize_count": number
          "seventh_prize_count": number
          "general_prize_count": number
          "no_prize_count": number
          "aggregate_sha256": string
        }
    "RequestValidationIssueView": {
          "location": string
          "type": string
        }
    "StrategyOverviewCapabilities": {
          "evaluation_metrics_available": boolean
          "d3_status_available": boolean
          "best_strategy_ranking_available": boolean
          "unavailable_reason_codes": Array<string>
        }
    "StrategyOverviewItem": {
          "strategy_id": string
          "display_name": string
          "version": string
          "supported_lottery_types": Array<components['schemas']["LotteryType"]>
          "minimum_history": number
          "lifecycle_status": components['schemas']["LifecycleStatus"]
          "executable": boolean
          "provenance": Array<string>
        }
    "StrategyOverviewResponse": {
          "items": Array<components['schemas']["StrategyOverviewItem"]>
          "summary": components['schemas']["StrategyOverviewSummary"]
          "capabilities": components['schemas']["StrategyOverviewCapabilities"]
        }
    "StrategyOverviewSummary": {
          "total": number
          "executable_count": number
          "metadata_only_count": number
          "lifecycle_counts": Record<string, number>
          "lottery_type_counts": Record<string, number>
        }
    "StrategyView": {
          "strategy_id": string
          "display_name": string
          "version": string
          "supported_lottery_types": Array<components['schemas']["LotteryType"]>
          "minimum_history": number
          "lifecycle_status": components['schemas']["LifecycleStatus"]
          "executable": boolean
        }
    "TicketCount": 10 | 15 | 20
  }
}
