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
  "/api/v1/historical-prefix-analytics/rankings": {
      get: {
          parameters: {
            "query": {
              "top_k"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixRankingsResponse"]
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
  "/api/v1/historical-prefix-analytics/strategies": {
      get: {
          parameters: {
            "query": {
              "prefix_count": components['schemas']["OverviewPrefixCount"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixStrategyOverviewResponse"]
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
  "/api/v1/historical-prefix-analytics/strategies/{strategy_id}/{strategy_version}/{replicate}/replay": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "prefix_count": components['schemas']["ReplayPrefixCount"]
              "limit"?: number
              "offset"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixReplayPageResponse"]
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
  "/api/v1/historical-prefix-success-windows": {
      get: {
          parameters: {
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
              "limit"?: number
              "offset"?: number
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixStrategySuccessWindowPageResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/random-null-baseline": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
              "window_kind": components['schemas']["WindowKind"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalSuccessRandomBaselineResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/research-qualification": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": Array<string>
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalSuccessResearchQualificationResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/research-qualification/random-baseline-evidence": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": Array<string>
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalSuccessQualificationRandomBaselineEvidenceResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/multi-import-concordance-census": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": Array<string>
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixMultiImportConcordanceCensusResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/cross-import-concordance": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "left_import_identity_sha256": string
              "right_import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixCrossImportConcordanceResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/recent-50-stability-audit": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixRecentStabilityAuditResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/temporal-holdout": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixTemporalHoldoutResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/feature-cohorts": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixStrategyFeatureCohortResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
              "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
              "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixStrategySuccessWindowResponse"]
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
  "/api/v1/historical-prefix-success-windows/strategies/{strategy_id}/{strategy_version}/{replicate}/matrix": {
      get: {
          parameters: {
            "path": {
              "strategy_id": string
              "strategy_version": string
              "replicate": number
            }
            "query": {
              "import_identity_sha256": string
            }
          }
          responses: {
                  200: {
                          content: {
                                    "application/json": components['schemas']["HistoricalPrefixStrategySuccessMatrixResponse"]
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
    "EvidenceStatus": "DESCRIPTIVE_ONLY" | "HISTORICAL_OOS_VERIFIED" | "CROSS_GAME_VERIFIED" | "SHADOW_CAPTURE" | "PRODUCTION_ELIGIBLE" | "REJECTED" | "NOT_READY"
    "ExactRatioView": {
          "numerator": number
          "denominator": number
          "is_available": boolean
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
    "HistoricalPerDrawPrefixMetricsView": {
          "identity": components['schemas']["HistoricalPrefixStrategyIdentityView"]
          "prefix_count": number
          "prefix_ticket_count": number
          "included_ticket_positions": Array<number>
          "best_single_main_hit_count": number
          "best_single_ticket_position": number
          "total_main_hit_count": number
          "portfolio_success": boolean
          "m3plus": boolean
          "m4plus": boolean
          "m5plus": boolean
          "m6": boolean
          "special_hit": boolean
          "special_hit_ticket_count": number
          "winning_ticket_count": number
          "no_prize_ticket_count": number
          "first_prize_ticket_count": number
          "second_prize_ticket_count": number
          "third_prize_ticket_count": number
          "fourth_prize_ticket_count": number
          "fifth_prize_ticket_count": number
          "sixth_prize_ticket_count": number
          "seventh_prize_ticket_count": number
          "general_prize_ticket_count": number
          "strongest_winning_tier": string
          "target": components['schemas']["HistoricalPrefixDrawIdentityView"]
          "cutoff": components['schemas']["HistoricalPrefixDrawIdentityView"]
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
    "HistoricalPrefixConfirmationOverlapRelation": "DISJOINT" | "PARTIAL_OVERLAP" | "IDENTICAL"
    "HistoricalPrefixConfirmationTargetOverlapView": {
          "left_confirmation_target_count": number
          "right_confirmation_target_count": number
          "overlap_count": number
          "left_only_count": number
          "right_only_count": number
          "relation": components['schemas']["HistoricalPrefixConfirmationOverlapRelation"]
        }
    "HistoricalPrefixCrossImportCohortComparisonView": {
          "cohort_index": number
          "feature_key": components['schemas']["HistoricalPrefixFeatureRelationTripleView"]
          "left_confirmation_diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
          "right_confirmation_diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
          "effect_change": components['schemas']["HistoricalPrefixSignedRateDeltaView"]
          "relationship": components['schemas']["HistoricalPrefixTemporalHoldoutRelationship"]
        }
    "HistoricalPrefixCrossImportConcordanceResponse": {
          "metadata": components['schemas']["HistoricalPrefixCrossImportMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "pair_status": components['schemas']["HistoricalPrefixCrossImportPairStatus"]
          "left_holdout_status": components['schemas']["HistoricalPrefixTemporalHoldoutStatus"]
          "right_holdout_status": components['schemas']["HistoricalPrefixTemporalHoldoutStatus"]
          "confirmation_target_overlap": components['schemas']["HistoricalPrefixConfirmationTargetOverlapView"] | null
          "comparisons": Array<components['schemas']["HistoricalPrefixCrossImportCohortComparisonView"]>
        }
    "HistoricalPrefixCrossImportMetadataView": {
          "left": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "right": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "same_dataset_sha256": boolean
          "same_source_artifact_sha256": boolean
        }
    "HistoricalPrefixCrossImportPairStatus": "COMPLETE" | "LEFT_NOT_READY" | "RIGHT_NOT_READY" | "BOTH_NOT_READY"
    "HistoricalPrefixDrawIdentityView": {
          "draw_number": number
          "draw_date": string
          "draw_sha256": string
        }
    "HistoricalPrefixExactProbabilityView": {
          "numerator": string
          "denominator": string
        }
    "HistoricalPrefixExactSuccessRateView": {
          "numerator": number
          "denominator": number
          "available": boolean
        }
    "HistoricalPrefixFeatureCohortDiagnosticView": {
          "cohort_index": number
          "feature_key": components['schemas']["HistoricalPrefixFeatureRelationTripleView"]
          "test_status": components['schemas']["HistoricalPrefixFeatureCohortTestStatus"]
          "cohort_counts": components['schemas']["HistoricalPrefixOutcomeCountsView"]
          "outside_counts": components['schemas']["HistoricalPrefixOutcomeCountsView"]
          "cohort_success_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
          "outside_success_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
          "risk_difference": components['schemas']["HistoricalPrefixSignedRateDeltaView"]
          "relation_vs_outside": components['schemas']["HistoricalPrefixRateRelation"]
          "raw_p_value": components['schemas']["HistoricalPrefixExactProbabilityView"]
          "adjusted_p_value": components['schemas']["HistoricalPrefixExactProbabilityView"]
          "first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
        }
    "HistoricalPrefixFeatureCohortTestStatus": "TESTED" | "NOT_TESTABLE_EMPTY_COHORT" | "NOT_TESTABLE_EMPTY_COMPLEMENT" | "NOT_TESTABLE_NO_OUTCOME_VARIATION"
    "HistoricalPrefixFeatureCohortView": {
          "feature_key": components['schemas']["HistoricalPrefixFeatureRelationTripleView"]
          "observation_count": number
          "success_count": number
          "failure_count": number
          "success_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
          "delta_vs_baseline": components['schemas']["HistoricalPrefixSignedRateDeltaView"]
          "relation_vs_baseline": components['schemas']["HistoricalPrefixRateRelation"]
          "first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
        }
    "HistoricalPrefixFeatureRelationTripleView": {
          "long_to_medium": components['schemas']["HistoricalPrefixRateRelation"]
          "medium_to_short": components['schemas']["HistoricalPrefixRateRelation"]
          "long_to_short": components['schemas']["HistoricalPrefixRateRelation"]
        }
    "HistoricalPrefixMetadataView": {
          "result_schema_version": string
          "source_import_identity_sha256": string
          "source_manifest_sha256": string
          "source_artifact_sha256": string
          "dataset_identity": string
          "dataset_sha256": string
          "lottery_type": string
          "ranking_policy_id": string
          "historical_only_disclaimer_id": string
        }
    "HistoricalPrefixMultiImportCensusStatus": "COMPLETE" | "PARTIAL_NOT_READY" | "ALL_NOT_READY"
    "HistoricalPrefixMultiImportCensusSummary": "ALL_AVAILABLE_HIGHER" | "ALL_AVAILABLE_EQUAL" | "ALL_AVAILABLE_LOWER" | "MIXED_AVAILABLE" | "PARTIAL_AVAILABILITY" | "NO_AVAILABLE_EFFECT"
    "HistoricalPrefixMultiImportCohortCensusRowView": {
          "cohort_index": number
          "feature_key": components['schemas']["HistoricalPrefixFeatureRelationTripleView"]
          "confirmation_diagnostics": Array<components['schemas']["HistoricalPrefixMultiImportConfirmationDiagnosticView"]>
          "higher_count": number
          "equal_count": number
          "lower_count": number
          "unavailable_count": number
          "summary": components['schemas']["HistoricalPrefixMultiImportCensusSummary"]
        }
    "HistoricalPrefixMultiImportConcordanceCensusResponse": {
          "imports": Array<components['schemas']["HistoricalPrefixMultiImportSourceView"]>
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "census_status": components['schemas']["HistoricalPrefixMultiImportCensusStatus"]
          "pair_count": number
          "pairs": Array<components['schemas']["HistoricalPrefixMultiImportPairView"]>
          "cohort_census_count": number
          "cohort_census": Array<components['schemas']["HistoricalPrefixMultiImportCohortCensusRowView"]>
        }
    "HistoricalPrefixMultiImportConfirmationDiagnosticView": {
          "import_index": number
          "import_identity_sha256": string
          "diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
        }
    "HistoricalPrefixMultiImportPairView": {
          "left_import_index": number
          "right_import_index": number
          "metadata": components['schemas']["HistoricalPrefixCrossImportMetadataView"]
          "pair_status": components['schemas']["HistoricalPrefixCrossImportPairStatus"]
          "left_holdout_status": components['schemas']["HistoricalPrefixTemporalHoldoutStatus"]
          "right_holdout_status": components['schemas']["HistoricalPrefixTemporalHoldoutStatus"]
          "confirmation_target_overlap": components['schemas']["HistoricalPrefixConfirmationTargetOverlapView"] | null
        }
    "HistoricalPrefixMultiImportSourceView": {
          "import_index": number
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "holdout_status": components['schemas']["HistoricalPrefixTemporalHoldoutStatus"]
        }
    "HistoricalPrefixOutcomeCountsView": {
          "observation_count": number
          "success_count": number
          "failure_count": number
        }
    "HistoricalPrefixRankingCandidateView": {
          "rank": number
          "identity": components['schemas']["HistoricalPrefixStrategyIdentityView"]
          "summary": components['schemas']["HistoricalPrefixStrategySummaryView"]
          "tie_break_provenance": Array<string>
        }
    "HistoricalPrefixRankingGroupView": {
          "prefix_count": number
          "status": string
          "total_candidate_count": number
          "requested_top_k": number
          "candidates": Array<components['schemas']["HistoricalPrefixRankingCandidateView"]>
        }
    "HistoricalPrefixRankingsResponse": {
          "metadata": components['schemas']["HistoricalPrefixMetadataView"]
          "top_k": number
          "groups": Array<components['schemas']["HistoricalPrefixRankingGroupView"]>
        }
    "HistoricalPrefixRateRelation": "HIGHER" | "EQUAL" | "LOWER" | "UNAVAILABLE"
    "HistoricalPrefixRecentStabilityAuditCohortComparisonView": {
          "cohort_index": number
          "feature_key": components['schemas']["HistoricalPrefixFeatureRelationTripleView"]
          "reference_diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
          "recent_diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
          "effect_change": components['schemas']["HistoricalPrefixSignedRateDeltaView"]
          "relationship": components['schemas']["HistoricalPrefixTemporalHoldoutRelationship"]
        }
    "HistoricalPrefixRecentStabilityAuditResponse": {
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "split": components['schemas']["HistoricalPrefixRecentStabilityAuditSplitView"]
          "audit_status": components['schemas']["HistoricalPrefixRecentStabilityAuditStatus"]
          "family_size": number
          "reference": components['schemas']["HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse"] | null
          "recent": components['schemas']["HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse"] | null
          "comparisons": Array<components['schemas']["HistoricalPrefixRecentStabilityAuditCohortComparisonView"]>
        }
    "HistoricalPrefixRecentStabilityAuditSplitView": {
          "source_temporal_split_method": string
          "audit_split_method": string
          "total_assignment_count": number
          "warmup_count": number
          "discovery_count": number
          "confirmation_count": number
          "reference_count": 0 | 250
          "recent_count": 0 | 50
          "discovery_first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "discovery_last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "confirmation_first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "confirmation_last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "reference_first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "reference_last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "recent_first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "recent_last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
        }
    "HistoricalPrefixRecentStabilityAuditStatus": "COMPLETE" | "NOT_READY_INSUFFICIENT_HISTORY"
    "HistoricalPrefixReplayPageResponse": {
          "metadata": components['schemas']["HistoricalPrefixMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixStrategyIdentityView"]
          "prefix_count": number
          "items": Array<components['schemas']["HistoricalPerDrawPrefixMetricsView"]>
          "total_count": number
          "limit": number
          "offset": number
        }
    "HistoricalPrefixSignedRateDeltaView": {
          "numerator": number
          "denominator": number
          "available": boolean
        }
    "HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse": {
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "baseline": components['schemas']["HistoricalPrefixWalkForwardBaselineView"]
          "family_size": number
          "raw_test_method": string
          "adjustment_method": string
          "diagnostics": Array<components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]>
        }
    "HistoricalPrefixStrategyFeatureCohortResponse": {
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "baseline": components['schemas']["HistoricalPrefixWalkForwardBaselineView"]
          "cohort_count": number
          "cohorts": Array<components['schemas']["HistoricalPrefixFeatureCohortView"]>
        }
    "HistoricalPrefixStrategyIdentityView": {
          "strategy_id": string
          "effective_strategy_id": string
          "strategy_version": string
          "replicate": number
          "identity_kind": string
          "governance_status": string
          "alias_of_strategy_id": string | null
          "equivalence_group": string | null
          "nested_prefix_supported": boolean
        }
    "HistoricalPrefixStrategyOverviewResponse": {
          "metadata": components['schemas']["HistoricalPrefixMetadataView"]
          "prefix_count": number
          "summaries": Array<components['schemas']["HistoricalPrefixStrategySummaryView"]>
          "total_count": number
        }
    "HistoricalPrefixStrategySuccessMatrixCellView": {
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "selection": components['schemas']["HistoricalPrefixSuccessSelectionIdentityView"]
          "status": string
          "source_observation_count": number
          "windows": Array<components['schemas']["HistoricalPrefixSuccessWindowSummaryView"]>
          "comparisons": Array<components['schemas']["HistoricalPrefixWindowRateComparisonView"]>
        }
    "HistoricalPrefixStrategySuccessMatrixResponse": {
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "source_observation_count": number
          "prefix_counts": Array<number>
          "criteria": Array<components['schemas']["HistoricalPrefixSuccessCriterionView"]>
          "cell_count": number
          "cells": Array<components['schemas']["HistoricalPrefixStrategySuccessMatrixCellView"]>
        }
    "HistoricalPrefixStrategySuccessWindowPageResponse": {
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "total_count": number
          "limit": number
          "offset": number
          "items": Array<components['schemas']["HistoricalPrefixStrategySuccessWindowResponse"]>
        }
    "HistoricalPrefixStrategySuccessWindowResponse": {
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "selection": components['schemas']["HistoricalPrefixSuccessSelectionIdentityView"]
          "status": string
          "source_observation_count": number
          "windows": Array<components['schemas']["HistoricalPrefixSuccessWindowSummaryView"]>
        }
    "HistoricalPrefixStrategySummaryView": {
          "identity": components['schemas']["HistoricalPrefixStrategyIdentityView"]
          "prefix_count": number
          "status": string
          "distinct_draw_count": number
          "replay_ticket_count": number
          "portfolio_success_count": number
          "portfolio_success_rate": components['schemas']["ExactRatioView"]
          "sum_best_main_hit_count": number
          "average_best_main_hit_count": components['schemas']["ExactRatioView"]
          "sum_total_main_hit_count": number
          "average_total_main_hit_count": components['schemas']["ExactRatioView"]
          "max_single_main_hit_count": number
          "max_portfolio_total_main_hit_count": number
          "max_hit_target": components['schemas']["HistoricalPrefixDrawIdentityView"] | null
          "m3plus_draw_count": number
          "m4plus_draw_count": number
          "m5plus_draw_count": number
          "m6_draw_count": number
          "special_hit_draw_count": number
          "special_hit_ticket_count": number
          "winning_draw_count": number
          "winning_ticket_count": number
          "no_prize_ticket_count": number
          "first_prize_ticket_count": number
          "second_prize_ticket_count": number
          "third_prize_ticket_count": number
          "fourth_prize_ticket_count": number
          "fifth_prize_ticket_count": number
          "sixth_prize_ticket_count": number
          "seventh_prize_ticket_count": number
          "general_prize_ticket_count": number
          "ranking_eligible": boolean
          "ranking_exclusion_reason": string | null
        }
    "HistoricalPrefixSuccessCriterion": "M3_PLUS" | "M4_PLUS" | "M5_PLUS" | "M6" | "M2_PLUS_SPECIAL" | "M3_PLUS_SPECIAL" | "M4_PLUS_SPECIAL" | "M5_PLUS_SPECIAL"
    "HistoricalPrefixSuccessCriterionView": {
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
          "minimum_main_hits": number
          "require_special_hit": boolean
          "measurement_mode": components['schemas']["MeasurementMode"]
        }
    "HistoricalPrefixSuccessDrawIdentityView": {
          "draw_number": number
          "draw_date": string
          "draw_sha256": string
        }
    "HistoricalPrefixSuccessPrefixCount": 1 | 2 | 3 | 4 | 5 | 10 | 15 | 20
    "HistoricalPrefixSuccessSelectionIdentityView": {
          "lottery": components['schemas']["LotteryType"]
          "strategy_id": string
          "strategy_version": string
          "replicate": number
          "ticket_count": number
          "max_bet_index": number
        }
    "HistoricalPrefixSuccessSourceMetadataView": {
          "run_id": string
          "contract_version": string
          "import_identity_sha256": string
          "source_kind": string
          "source_repository": string
          "source_commit_oid": string
          "source_artifact_sha256": string
          "dataset_identity": string
          "dataset_sha256": string
          "lottery_type": string
        }
    "HistoricalPrefixSuccessStrategyIdentityView": {
          "strategy_id": string
          "effective_strategy_id": string
          "strategy_version": string
          "replicate": number
          "identity_kind": string
          "governance_status": string
          "alias_of_strategy_id": string | null
          "equivalence_group": string | null
          "nested_prefix_supported": boolean
          "descriptor_sha256": string
        }
    "HistoricalPrefixSuccessWindowSummaryView": {
          "window_kind": components['schemas']["WindowKind"]
          "window_role": components['schemas']["WindowRole"]
          "requested_draw_count": number | null
          "source_draw_count": number
          "eligible_draw_count": number
          "excluded_draw_count": number
          "success_count": number
          "failure_count": number
          "success_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
          "first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"]
          "last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"]
          "first_cutoff": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"]
          "last_cutoff": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"]
          "nested_windows_independent": boolean
          "evaluation_status": components['schemas']["WindowEvaluationStatus"]
          "evidence_status": components['schemas']["EvidenceStatus"]
        }
    "HistoricalPrefixTemporalHoldoutCohortComparisonView": {
          "cohort_index": number
          "feature_key": components['schemas']["HistoricalPrefixFeatureRelationTripleView"]
          "discovery_diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
          "confirmation_diagnostic": components['schemas']["HistoricalPrefixFeatureCohortDiagnosticView"]
          "effect_change": components['schemas']["HistoricalPrefixSignedRateDeltaView"]
          "relationship": components['schemas']["HistoricalPrefixTemporalHoldoutRelationship"]
        }
    "HistoricalPrefixTemporalHoldoutRelationship": "SAME_HIGHER" | "SAME_EQUAL" | "SAME_LOWER" | "DIFFERENT" | "UNAVAILABLE"
    "HistoricalPrefixTemporalHoldoutResponse": {
          "metadata": components['schemas']["HistoricalPrefixSuccessSourceMetadataView"]
          "strategy": components['schemas']["HistoricalPrefixSuccessStrategyIdentityView"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterionView"]
          "prefix_count": number
          "split": components['schemas']["HistoricalPrefixTemporalHoldoutSplitView"]
          "evaluation_status": components['schemas']["HistoricalPrefixTemporalHoldoutStatus"]
          "family_size": number
          "discovery": components['schemas']["HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse"] | null
          "confirmation": components['schemas']["HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse"] | null
          "comparisons": Array<components['schemas']["HistoricalPrefixTemporalHoldoutCohortComparisonView"]>
        }
    "HistoricalPrefixTemporalHoldoutSplitView": {
          "split_method": string
          "total_assignment_count": number
          "warmup_count": number
          "discovery_count": number
          "confirmation_count": number
          "discovery_first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "discovery_last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "confirmation_first_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
          "confirmation_last_target": components['schemas']["HistoricalPrefixSuccessDrawIdentityView"] | null
        }
    "HistoricalPrefixTemporalHoldoutStatus": "COMPLETE" | "NOT_READY_INSUFFICIENT_HISTORY"
    "HistoricalPrefixWalkForwardBaselineView": {
          "observation_count": number
          "success_count": number
          "failure_count": number
          "success_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
        }
    "HistoricalPrefixWindowRateComparisonKind": "FULL_HISTORY_TO_LONG" | "LONG_TO_MEDIUM" | "MEDIUM_TO_SHORT" | "LONG_TO_SHORT"
    "HistoricalPrefixWindowRateComparisonView": {
          "comparison_kind": components['schemas']["HistoricalPrefixWindowRateComparisonKind"]
          "from_window_kind": components['schemas']["WindowKind"]
          "to_window_kind": components['schemas']["WindowKind"]
          "from_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
          "to_rate": components['schemas']["HistoricalPrefixExactSuccessRateView"]
          "delta": components['schemas']["HistoricalPrefixSignedRateDeltaView"]
          "relation": components['schemas']["HistoricalPrefixRateRelation"]
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
    "HistoricalSuccessQualificationCensusStatus": "COMPLETE" | "PARTIAL_NOT_READY" | "ALL_NOT_READY"
    "HistoricalSuccessQualificationEvidenceStatus": "COMPLETE" | "NOT_READY"
    "HistoricalSuccessQualificationIdentityView": {
          "strategy_id": string
          "strategy_version": string
          "replicate": number
          "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
        }
    "HistoricalSuccessQualificationImportEvidenceView": {
          "import_index": number
          "import_identity_sha256": string
          "dataset_sha256": string
          "source_artifact_sha256": string
          "source_observation_count": number
          "strategy_window_status": components['schemas']["HistoricalSuccessQualificationEvidenceStatus"]
          "temporal_holdout_status": components['schemas']["HistoricalSuccessQualificationEvidenceStatus"]
          "recent_audit_status": components['schemas']["HistoricalSuccessQualificationEvidenceStatus"]
          "recent_relationship_difference_count": number
        }
    "HistoricalSuccessQualificationInformationalFlag": "CROSS_IMPORT_UNRESOLVED" | "HISTORICAL_CONCORDANCE_OBSERVED" | "RECENT_RELATIONSHIP_DIFFERENCE"
    "HistoricalSuccessQualificationOverlapRelation": "DISJOINT" | "PARTIAL_OVERLAP" | "IDENTICAL"
    "HistoricalSuccessQualificationPairEvidenceView": {
          "left_import_index": number
          "right_import_index": number
          "pair_status": components['schemas']["HistoricalSuccessQualificationPairStatus"]
          "same_dataset_sha256": boolean
          "same_source_artifact_sha256": boolean
          "confirmation_overlap_relation": components['schemas']["HistoricalSuccessQualificationOverlapRelation"] | null
          "r1_comparable": boolean
        }
    "HistoricalSuccessQualificationPairStatus": "COMPLETE" | "LEFT_NOT_READY" | "RIGHT_NOT_READY" | "BOTH_NOT_READY"
    "HistoricalSuccessQualificationPrimaryStatus": "NOT_READY" | "EVIDENCE_INCOMPLETE" | "RESEARCH_CANDIDATE"
    "HistoricalSuccessQualificationRandomAvailabilityStatus": "COMPLETE" | "PARTIAL" | "ALL_NOT_READY"
    "HistoricalSuccessQualificationRandomBaselineAvailabilityView": {
          "availability_status": components['schemas']["HistoricalSuccessQualificationRandomAvailabilityStatus"]
          "evaluated_cell_count": number
          "ready_cell_count": number
          "raw_upper_tail_probability_count": number
          "multiple_testing_warning": string
        }
    "HistoricalSuccessQualificationRandomBaselineCellView": {
          "import_index": number
          "window_index": number
          "qualification_random_role": components['schemas']["HistoricalSuccessQualificationRandomRole"]
          "baseline": components['schemas']["HistoricalSuccessRandomBaselineResponse"]
        }
    "HistoricalSuccessQualificationRandomBaselineEvidenceResponse": {
          "qualification_identity": components['schemas']["HistoricalSuccessQualificationIdentityView"]
          "ordered_import_identity_sha256s": Array<string>
          "availability_summary": components['schemas']["HistoricalSuccessQualificationRandomBaselineAvailabilityView"]
          "ordered_cells": Array<components['schemas']["HistoricalSuccessQualificationRandomBaselineCellView"]>
        }
    "HistoricalSuccessQualificationRandomRole": "REFERENCE_ONLY" | "PRIMARY_DESCRIPTIVE_COMPARISON" | "CONFIRMATION_DESCRIPTIVE_COMPARISON" | "AUDIT_ONLY_NON_BLOCKING"
    "HistoricalSuccessRandomBaselineCellView": {
          "policy_version": string
          "import_identity_sha256": string
          "dataset_sha256": string
          "source_artifact_sha256": string
          "strategy_id": string
          "strategy_version": string
          "replicate": number
          "window_kind": components['schemas']["WindowKind"]
          "window_policy_version": string
          "prefix_count": components['schemas']["HistoricalPrefixSuccessPrefixCount"]
          "criterion": components['schemas']["HistoricalPrefixSuccessCriterion"]
        }
    "HistoricalSuccessRandomBaselineExactRationalView": {
          "numerator": string
          "denominator": string
          "decimal_18": string
        }
    "HistoricalSuccessRandomBaselineNotReadyReason": "NO_OBSERVATIONS" | "WINDOW_INCOMPLETE" | "EXCLUDED_OBSERVATIONS" | "SOURCE_TICKET_SEMANTICS_CONFLICT" | "EXACT_COMPUTATION_UNAVAILABLE"
    "HistoricalSuccessRandomBaselineReadiness": "READY" | "NOT_READY"
    "HistoricalSuccessRandomBaselineResponse": {
          "cell": components['schemas']["HistoricalSuccessRandomBaselineCellView"]
          "readiness": components['schemas']["HistoricalSuccessRandomBaselineReadiness"]
          "reason_codes": Array<components['schemas']["HistoricalSuccessRandomBaselineNotReadyReason"]>
          "sampling_policy": components['schemas']["HistoricalSuccessRandomBaselineSamplingPolicy"]
          "ticket_count_interpretation": string
          "legal_ticket_count": string
          "success_ticket_count": string
          "portfolio_success_probability": components['schemas']["HistoricalSuccessRandomBaselineExactRationalView"]
          "eligible_observation_count": number
          "excluded_observation_count": number
          "observed_success_count": number | null
          "expected_successes": components['schemas']["HistoricalSuccessRandomBaselineExactRationalView"] | null
          "upper_tail_probability": components['schemas']["HistoricalSuccessRandomBaselineExactRationalView"] | null
          "observed_ticket_position_count": number
          "observed_distinct_ticket_count": number
          "observed_duplicate_ticket_count": number
          "observation_count_with_duplicates": number
          "interpretation_caveat": string
        }
    "HistoricalSuccessRandomBaselineSamplingPolicy": "UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT"
    "HistoricalSuccessResearchQualificationResponse": {
          "identity": components['schemas']["HistoricalSuccessQualificationIdentityView"]
          "ordered_import_evidence": Array<components['schemas']["HistoricalSuccessQualificationImportEvidenceView"]>
          "primary_status": components['schemas']["HistoricalSuccessQualificationPrimaryStatus"]
          "informational_flags": Array<components['schemas']["HistoricalSuccessQualificationInformationalFlag"]>
          "random_baseline_caveat": string | null
          "comparable_import_count": number
          "expected_pair_count": number
          "actual_pair_count": number
          "census_status": components['schemas']["HistoricalSuccessQualificationCensusStatus"]
          "cohort_census_count": number
          "pair_evidence": Array<components['schemas']["HistoricalSuccessQualificationPairEvidenceView"]>
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
    "MeasurementMode": "CANDIDATE_COVERAGE" | "LEGAL_TICKET_PRIZE" | "OFFICIAL_PRIZE_TIER"
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
    "OverviewPrefixCount": 10 | 15 | 20
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
    "ReplayPrefixCount": 1 | 2 | 3 | 4 | 5 | 10 | 15 | 20
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
    "WindowEvaluationStatus": "COMPLETE" | "INSUFFICIENT_DRAWS" | "NO_ELIGIBLE_DRAWS"
    "WindowKind": "FULL_HISTORY" | "LONG" | "MEDIUM" | "SHORT"
    "WindowRole": "REFERENCE_ONLY" | "PRIMARY_EVIDENCE" | "STABILITY_CONFIRMATION" | "DEGRADATION_VETO" | "PROMOTION_FILTER"
  }
}
