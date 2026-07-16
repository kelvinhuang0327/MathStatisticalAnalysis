// Generated from contracts/openapi.json. Do not edit by hand.
// OpenAPI 3.1.0; LottoLab API 0.1.0

export interface paths {
  "/api/health": {
      get: {
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
          responses: {
                  200: {
                          content: {
                                    "application/json": Array<components['schemas']["StrategyView"]>
                                  }
                        }
                }
        }
    }
  "/api/v1/draw-imports/preview": {
      post: {
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
    "RequestValidationIssueView": {
          "location": string
          "type": string
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
  }
}
