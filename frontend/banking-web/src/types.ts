// Chat types
export type Role = 'user' | 'assistant'

export interface Message {
  id: string
  role: Role
  content: string
}

// Account types
export interface AccountInfo {
  account_id: string
  username: string
  full_name: string
  email: string
}

export interface AccountDetails {
  account_id: string
  account_type: string
  balance: number
  currency: string
  status: string
}

export interface PaymentMethod {
  payment_method_id: string
  type: string
  last4: string
  brand: string
}

// Transaction types
export interface Transaction {
  transaction_id: string
  account_id: string
  recipient_id: string
  amount: number
  currency: string
  description: string
  category: string
  status: string
  timestamp: string
}

// Payment types
export interface PaymentRequest {
  account_id: string
  beneficiary_id: string
  amount: number
  currency: string
  reference: string
}

export interface PaymentResponse {
  confirmation_id: string
  account_id: string
  beneficiary_id: string
  amount: number
  currency: string
  reference: string
  status: string
  timestamp: string
}

export interface Beneficiary {
  beneficiary_id: string
  name: string
  account_number: string
  bank: string
}
