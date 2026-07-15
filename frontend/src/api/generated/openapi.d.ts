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
}

export interface components {
  schemas: {
    "LifecycleStatus": "IDEA" | "OBSERVATION" | "ONLINE" | "REJECTED" | "RETIRED"
    "LotteryType": "DAILY_539" | "BIG_LOTTO" | "POWER_LOTTO"
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
