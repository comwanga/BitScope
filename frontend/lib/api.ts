export type HealthResponse = {
  status: string;
  app: string;
  network: string;
  rpc_configured: boolean;
  version: string;
};

export type NodeStatusResponse = {
  chain: string | null;
  blocks: number | null;
  headers: number | null;
  best_block_hash: string | null;
  verification_progress: number | null;
  initial_block_download: boolean | null;
  difficulty: number | null;
  pruned: boolean | null;
  size_on_disk: number | null;
  network_active: boolean | null;
  peer_count: number | null;
  mempool_tx_count: number | null;
  mempool_usage: number | null;
  mempool_min_fee: number | null;
  incremental_relay_fee: number | null;
  relay_fee: number | null;
  warnings: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type LiveNodeEvent = {
  timestamp: string;
  chain: string | null;
  blocks: number | null;
  headers: number | null;
  verification_progress: number | null;
  initial_block_download: boolean | null;
  peer_count: number | null;
  network_active: boolean | null;
  mempool_tx_count: number | null;
  mempool_usage: number | null;
  warnings: string[];
};

export type ZmqStatusResponse = {
  configured: boolean;
  rawblock_endpoint: string | null;
  rawtx_endpoint: string | null;
  sse_endpoint: string;
  zmq_listener_available: boolean;
  recommended_bitcoin_conf: string[];
  warnings: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RpcLanguageExample = {
  language: string;
  title: string;
  description: string;
  code: string;
};

export type RpcExamplesResponse = {
  rpc_url: string;
  wallet_rpc_path: string;
  examples: RpcLanguageExample[];
  zmq_conf: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
};

export type KeySafetyModel = {
  handles_private_keys: boolean;
  allowed_inputs: string[];
  blocked_inputs: string[];
  message: string;
};

export type DerivationPathInfo = {
  purpose: string;
  path: string;
  descriptor: string;
  script_type: string;
  notes: string;
};

export type DescriptorRecipe = {
  name: string;
  descriptor: string;
  change_descriptor: string;
  purpose: string;
};

export type PsbtFlowStep = {
  step: number;
  role: string;
  action: string;
  bitcoin_core_rpc: string;
  private_key_boundary: string;
};

export type KeyEducationResponse = {
  safety_model: KeySafetyModel;
  derivation_paths: DerivationPathInfo[];
  descriptor_recipes: DescriptorRecipe[];
  psbt_flow: PsbtFlowStep[];
  watch_only_commands: string[];
  hardware_wallet_notes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
};

export type DemoStep = {
  id: string;
  title: string;
  status: string;
  summary: string;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  raw: Record<string, unknown>;
};

export type DemoRunResponse = {
  session_id: string;
  wallet_name: string;
  mining_address: string;
  recipient_address: string;
  txid: string | null;
  block_hashes: string[];
  confirmation_block_hashes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  steps: DemoStep[];
  export_markdown: string;
  explanation: string;
};

export type PeerNetwork = {
  name: string | null;
  limited: boolean | null;
  reachable: boolean | null;
  proxy: string | null;
  proxy_randomize_credentials: boolean | null;
};

export type LocalAddress = {
  address: string | null;
  port: number | null;
  score: number | null;
  network: string | null;
};

export type PeerInfo = {
  id: number | null;
  addr: string | null;
  addr_bind: string | null;
  addr_local: string | null;
  network: string | null;
  inbound: boolean | null;
  relay_transactions: boolean | null;
  services: string | null;
  services_names: string[];
  subver: string | null;
  starting_height: number | null;
  synced_headers: number | null;
  synced_blocks: number | null;
  ping_time: number | null;
  min_ping: number | null;
  connection_type: string | null;
  permissions: string[];
  bytes_sent: number | null;
  bytes_received: number | null;
};

export type PeerSummaryResponse = {
  peer_count: number;
  inbound_count: number;
  outbound_count: number;
  tor_peer_count: number;
  i2p_peer_count: number;
  local_address_count: number;
  network_active: boolean | null;
  reachable_networks: Array<string | null>;
  networks: PeerNetwork[];
  local_addresses: LocalAddress[];
  peers: PeerInfo[];
  warnings: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type BlockResponse = {
  query: string;
  query_type: string;
  height: number | null;
  hash: string;
  confirmations: number | null;
  timestamp: number | null;
  previous_block_hash: string | null;
  next_block_hash: string | null;
  merkle_root: string | null;
  version: number | null;
  version_hex: string | null;
  difficulty: number | null;
  nonce: number | null;
  bits: string | null;
  size: number | null;
  stripped_size: number | null;
  weight: number | null;
  transaction_count: number;
  transaction_ids: string[];
  merkle_layers: MerkleLayer[];
  merkle_verified: boolean | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type MerkleNode = {
  hash: string;
  duplicated: boolean;
};

export type MerkleLayer = {
  level: number;
  label: string;
  nodes: MerkleNode[];
};

export type TransactionInput = {
  coinbase: string | null;
  previous_txid: string | null;
  vout: number | null;
  sequence: number | null;
  script_sig_asm: string | null;
  script_sig_hex: string | null;
  witness: string[];
};

export type TransactionOutput = {
  n: number;
  value_btc: number;
  script_pub_key_asm: string | null;
  script_pub_key_hex: string | null;
  script_type: string | null;
  address: string | null;
};

export type TransactionResponse = {
  txid: string;
  hash: string | null;
  version: number | null;
  size: number | null;
  vsize: number | null;
  weight: number | null;
  locktime: number | null;
  confirmations: number | null;
  block_hash: string | null;
  block_time: number | null;
  time: number | null;
  in_mempool: boolean;
  fee_btc: number | null;
  fee_source: string | null;
  inputs: TransactionInput[];
  outputs: TransactionOutput[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RegtestTransactionBuildResponse = {
  wallet_name: string;
  address: string;
  amount_btc: number;
  unsigned_hex: string;
  funded_hex: string;
  signed_hex: string | null;
  complete: boolean;
  txid: string | null;
  fee_btc: number | null;
  change_position: number | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RegtestTransactionSendResponse = RegtestTransactionBuildResponse & {
  txid: string;
  confirmation_block_hashes: string[];
};

export type TransactionPolicyResponse = {
  txid: string;
  in_mempool: boolean;
  bip125_replaceable: boolean | null;
  can_rbf: boolean;
  can_cpfp: boolean;
  fee_btc: number | null;
  modified_fee_btc: number | null;
  vsize: number | null;
  fee_rate_sat_vb: number | null;
  ancestor_count: number | null;
  ancestor_size: number | null;
  ancestor_fees_btc: number | null;
  descendant_count: number | null;
  descendant_size: number | null;
  descendant_fees_btc: number | null;
  warnings: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RbfBumpResponse = {
  wallet_name: string;
  original_txid: string;
  replacement_txid: string | null;
  original_fee_btc: number | null;
  replacement_fee_btc: number | null;
  fee_delta_btc: number | null;
  errors: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type CpfpChildResponse = {
  wallet_name: string;
  parent_txid: string;
  parent_vout: number;
  destination_address: string;
  amount_btc: number;
  unsigned_hex: string;
  funded_hex: string;
  signed_hex: string | null;
  complete: boolean;
  child_txid: string | null;
  fee_btc: number | null;
  change_position: number | null;
  broadcast: boolean;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type MultisigCreateResponse = {
  wallet_name: string;
  required_signatures: number;
  signer_count: number;
  address_type: string;
  source_addresses: string[];
  pubkeys: string[];
  multisig_address: string;
  redeem_script: string | null;
  descriptor: string | null;
  warnings: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type MultisigFundResponse = {
  wallet_name: string;
  multisig_address: string;
  amount_btc: number;
  txid: string;
  confirmation_block_hashes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type MultisigSpendResponse = {
  wallet_name: string;
  multisig_address: string;
  destination_address: string;
  amount_btc: number;
  input_count: number;
  psbt: string;
  processed_psbt: string;
  complete: boolean;
  hex: string | null;
  final_psbt: string | null;
  fee_btc: number | null;
  change_position: number | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type LocktimeTransactionResponse = {
  wallet_name: string;
  destination_address: string;
  amount_btc: number;
  locktime: number;
  sequence: number;
  unsigned_hex: string;
  funded_hex: string;
  sequence_hex: string;
  signed_hex: string | null;
  complete: boolean;
  txid: string | null;
  fee_btc: number | null;
  change_position: number | null;
  mempool_accept: unknown;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type TimelockScriptResponse = {
  mode: string;
  value: number;
  pubkey_hex: string;
  script_hex: string;
  asm: string | null;
  p2sh: string | null;
  segwit: Record<string, unknown> | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type MempoolSummaryResponse = {
  transaction_count: number | null;
  virtual_size: number | null;
  total_fee_btc: number | null;
  mempool_min_fee: number | null;
  incremental_relay_fee: number | null;
  memory_usage: number | null;
  max_mempool: number | null;
  sample_transaction_ids: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type MempoolEntryResponse = {
  txid: string;
  vsize: number | null;
  weight: number | null;
  time: number | null;
  height: number | null;
  descendant_count: number | null;
  descendant_size: number | null;
  ancestor_count: number | null;
  ancestor_size: number | null;
  fee_btc: number | null;
  modified_fee_btc: number | null;
  depends: string[];
  spent_by: string[];
  bip125_replaceable: boolean | null;
  unbroadcast: boolean | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type FeeEstimate = {
  target_blocks: number;
  btc_per_kvb: number | null;
  sats_per_vbyte: number | null;
  available: boolean;
  errors: string[];
};

export type FeeEstimateResponse = {
  estimates: FeeEstimate[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type AddressUtxo = {
  txid: string;
  vout: number;
  amount_btc: number;
  confirmations: number;
  spendable: boolean | null;
  solvable: boolean | null;
  safe: boolean | null;
  descriptor: string | null;
};

export type AddressResponse = {
  address: string;
  is_valid: boolean;
  network: string | null;
  address_type: string | null;
  script_pub_key: string | null;
  witness_version: number | null;
  witness_program: string | null;
  is_mine: boolean | null;
  is_watch_only: boolean | null;
  solvable: boolean | null;
  wallet_name: string | null;
  received_btc: number | null;
  utxos: AddressUtxo[];
  limitation: string | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type IndexedAddressOutput = {
  txid: string;
  vout: number;
  value_btc: number;
  block_height: number;
  block_hash: string;
  script_type: string | null;
  script_pub_key_hex: string | null;
};

export type AddressIndexScanResponse = {
  address: string;
  start_height: number;
  end_height: number;
  blocks_scanned: number;
  outputs: IndexedAddressOutput[];
  total_received_btc_in_range: number;
  limitation: string;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type DescriptorAnalyzeResponse = {
  descriptor: string;
  normalized_descriptor: string | null;
  checksum: string | null;
  is_range: boolean | null;
  is_solvable: boolean | null;
  has_private_keys: boolean | null;
  derived_addresses: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletDescriptorInfo = {
  descriptor: string;
  active: boolean | null;
  internal: boolean | null;
  range: number[] | null;
  next_index: number | null;
  timestamp: number | string | null;
};

export type WalletDescriptorsResponse = {
  wallet_name: string;
  descriptors: WalletDescriptorInfo[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletInfo = {
  wallet_name: string;
  loaded: boolean;
  scanning: boolean | null;
  private_keys_enabled: boolean | null;
  descriptors: boolean | null;
  blank: boolean | null;
  birthtime: number | null;
  warnings: string[];
};

export type WalletSummaryResponse = {
  loaded_wallets: string[];
  available_wallets: WalletInfo[];
  configured_wallet: string | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletActionResponse = {
  wallet_name: string;
  message: string;
  warning: string | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletBalanceResponse = {
  wallet_name: string;
  trusted_btc: number | null;
  untrusted_pending_btc: number | null;
  immature_btc: number | null;
  total_btc: number | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletAddressResponse = {
  wallet_name: string;
  address: string;
  label: string;
  address_type: string;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletUtxo = {
  txid: string;
  vout: number;
  address: string | null;
  label: string | null;
  amount_btc: number;
  confirmations: number;
  spendable: boolean | null;
  solvable: boolean | null;
  safe: boolean | null;
};

export type WalletUtxosResponse = {
  wallet_name: string;
  utxos: WalletUtxo[];
  total_btc: number;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type WalletTransaction = {
  txid: string;
  category: string | null;
  address: string | null;
  amount_btc: number | null;
  fee_btc: number | null;
  confirmations: number | null;
  time: number | null;
  trusted: boolean | null;
};

export type WalletTransactionsResponse = {
  wallet_name: string;
  transactions: WalletTransaction[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RegtestMineResponse = {
  blocks: number;
  address: string;
  wallet_name: string | null;
  block_hashes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RegtestFaucetResponse = {
  txid: string;
  wallet_name: string;
  address: string;
  amount_btc: number;
  trusted_balance_btc: number;
  immature_balance_btc: number;
  confirmation_block_hashes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type ScriptOpcode = {
  offset: number;
  opcode: string;
  data_hex: string | null;
  data_length: number | null;
  description: string;
};

export type DecodeScriptResponse = {
  script_hex: string;
  asm: string | null;
  script_type: string | null;
  req_sigs: number | null;
  addresses: string[];
  p2sh: string | null;
  segwit: Record<string, unknown> | null;
  opcodes: ScriptOpcode[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type ScriptTemplateResponse = {
  template: string;
  script_hex: string;
  asm: string | null;
  script_type: string | null;
  p2sh: string | null;
  segwit: Record<string, unknown> | null;
  opcodes: ScriptOpcode[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type ScriptTestResponse = {
  transaction_hex: string;
  accepted: boolean | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type OpReturnTransactionResponse = {
  wallet_name: string;
  data_format: string;
  data_hex: string;
  data_utf8: string | null;
  data_bytes: number;
  op_return_script_hex: string;
  destination_address: string | null;
  amount_btc: number | null;
  unsigned_hex: string;
  funded_hex: string;
  signed_hex: string | null;
  complete: boolean;
  txid: string | null;
  fee_btc: number | null;
  change_position: number | null;
  mempool_accept: unknown;
  broadcast: boolean;
  confirmation_block_hashes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type TaprootInspectResponse = {
  address: string | null;
  script_hex: string | null;
  is_taproot: boolean;
  witness_version: number | null;
  witness_program: string | null;
  output_key: string | null;
  script_type: string | null;
  asm: string | null;
  notes: string[];
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type PsbtDecodeResponse = {
  psbt: string;
  txid: string | null;
  input_count: number;
  output_count: number;
  fee_btc: number | null;
  is_complete: boolean | null;
  next_role: string | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type PsbtCreateResponse = {
  wallet_name: string;
  psbt: string;
  fee_btc: number | null;
  change_position: number | null;
  recipient_address: string;
  amount_btc: number;
  decoded: PsbtDecodeResponse | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type PsbtProcessResponse = {
  wallet_name: string;
  psbt: string;
  complete: boolean;
  signed: boolean;
  decoded: PsbtDecodeResponse | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type PsbtFinalizeResponse = {
  complete: boolean;
  psbt: string | null;
  hex: string | null;
  cli_commands: string[];
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type RpcMethodInfo = {
  name: string;
  category: string;
  description: string;
  example_params: unknown[] | Record<string, unknown>;
  concepts: string[];
};

export type RpcMethodsResponse = {
  methods: RpcMethodInfo[];
  cli_command: string;
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
};

export type RpcExecuteResponse = {
  method: string;
  category: string;
  params: unknown[] | Record<string, unknown>;
  result: unknown;
  cli_command: string;
  rpc_methods: string[];
  concepts: string[];
  explanation: string;
  raw: Record<string, unknown>;
};

export type LearningConcept = {
  id: string;
  title: string;
  category: string;
  summary: string;
  details: string;
  related_rpc_methods: string[];
  related_pages: string[];
  cli_examples: string[];
  cautions: string[];
};

export type LearningConceptsResponse = {
  concepts: LearningConcept[];
  categories: string[];
  rpc_methods: string[];
  explanation: string;
};

export type LearningRpcMethodsResponse = {
  methods: RpcMethodInfo[];
  explanation: string;
};

export type CurriculumEntry = {
  chapter: number;
  title: string;
  source_url: string;
  learning_objective: string;
  relevant_pages: string[];
  relevant_scenarios: string[];
  rpc_methods: string[];
  prerequisites: string[];
  guided_exercise: string;
  independent_challenge: string;
  verification_criteria: string[];
  implementation_note: string | null;
};

export type CurriculumResponse = {
  schema_version: 1;
  course_title: string;
  course_url: string;
  chapters: CurriculumEntry[];
  explanation: string;
};

export type ChallengeDefinition = {
  challenge_id: string;
  version: string;
  title: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  objective: string;
  allowed_actions: string[];
  relevant_pages: string[];
  scenario_id: string;
  hint_count: number;
  verification_summary: string;
  solution_locked: true;
};

export type ChallengeCatalogResponse = {
  schema_version: 1;
  challenges: ChallengeDefinition[];
  explanation: string;
};

export type ChallengeHint = {
  challenge_id: string;
  level: number;
  hint: string;
  remaining_hints: number;
  reveals_solution: false;
};

export type ChallengeVerificationCheck = {
  check_id: string;
  passed: boolean;
  explanation: string;
  evidence_ids: string[];
};

export type ChallengeVerificationResult = {
  schema_version: 1;
  challenge_id: string;
  challenge_version: string;
  run_id: string;
  lab_session_id: string;
  scenario_id: string;
  scenario_version: string;
  bitcoin_core_version: string | null;
  verified_at: string;
  completed: boolean;
  validation_source: "persisted_bitcoin_core_scenario_evidence";
  checks: ChallengeVerificationCheck[];
  evidence: Array<{ evidence_id: string; kind: string; content_sha256: string }>;
  final_explanation: string;
  solution_unlocked: boolean;
};

export type ApiError = {
  error: true;
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type LifecycleEventType =
  | "wallet_prepared"
  | "utxo_selected"
  | "raw_transaction_created"
  | "transaction_funded"
  | "psbt_created"
  | "psbt_partially_signed"
  | "psbt_completed"
  | "transaction_finalized"
  | "mempool_preflight_completed"
  | "transaction_broadcast"
  | "transaction_entered_mempool"
  | "transaction_replaced"
  | "child_transaction_created"
  | "transaction_confirmed"
  | "timelock_matured"
  | "scenario_cleaned_up";

export type LifecycleRelationship = {
  relationship_type: "replaces" | "replaced_by" | "child_of" | "parent_of" | "conflicts_with";
  related_txid: string;
  explanation: string;
};

export type TransactionLifecycleEvent = {
  schema_version: 1;
  event_id: string;
  ordinal: number;
  event_type: LifecycleEventType;
  timestamp: string;
  step_id: string;
  track_id: string;
  transaction_state: string;
  transaction_id: string | null;
  transaction_hex_ref: string | null;
  psbt_ref: string | null;
  fee_btc: string | number | null;
  fee_rate_sat_vb: string | number | null;
  locktime: number | null;
  sequence_values: number[];
  relationship: LifecycleRelationship | null;
  block_height: number | null;
  explanation: string;
  rpc_method: string;
  cli_command: {
    executable: "bitcoin-cli";
    arguments: string[];
    description: string;
  };
  evidence_id: string;
  raw_safe_core_result: unknown;
};

export type TransactionLifecycleTimeline = {
  schema_version: 1;
  run_id: string;
  scenario_id: string;
  scenario_version: string;
  lab_session_id: string;
  generated_at: string;
  events: TransactionLifecycleEvent[];
};

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const LOCAL_ACCESS_TOKEN = process.env.NEXT_PUBLIC_BITSCOPE_LOCAL_ACCESS_TOKEN ?? "";

const MUTATION_PATHS = new Set([
  "/demo/run",
  "/multisig/create",
  "/multisig/fund",
  "/multisig/spend-psbt",
  "/psbt/create",
  "/psbt/wallet-process",
  "/regtest/mine",
  "/regtest/faucet",
  "/scripts/create-op-return",
  "/timelocks/transaction",
  "/transactions/create-regtest",
  "/transactions/send-regtest",
  "/transactions/rbf-bump",
  "/transactions/cpfp-child",
  "/wallets/create",
  "/wallets/load"
]);

export function liveNodeEventsUrl(intervalSeconds = 3): string {
  const url = new URL(`${API_BASE_URL}/live/node`);
  url.searchParams.set("interval_seconds", String(intervalSeconds));
  return url.toString();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    next: { revalidate: 5 }
  });

  if (!response.ok) {
    let message = "BitScope backend is not reachable.";
    try {
      const payload = (await response.json()) as ApiError;
      message = payload.message ?? message;
    } catch {
      // Keep the default message if the backend returned non-JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<HealthResponse>;
}

export async function fetchNodeStatus(): Promise<NodeStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/node/status`, {
    next: { revalidate: 5 }
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Bitcoin Core node status is not available."));
  }

  return response.json() as Promise<NodeStatusResponse>;
}

export async function fetchPeers(): Promise<PeerSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/peers`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Peer and network data could not be loaded."));
  }

  return response.json() as Promise<PeerSummaryResponse>;
}

export async function fetchZmqStatus(): Promise<ZmqStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/live/zmq`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "ZMQ integration status could not be loaded."));
  }

  return response.json() as Promise<ZmqStatusResponse>;
}

export async function fetchRpcExamples(): Promise<RpcExamplesResponse> {
  const response = await fetch(`${API_BASE_URL}/integrations/rpc-examples`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "RPC integration examples could not be loaded."));
  }

  return response.json() as Promise<RpcExamplesResponse>;
}

export async function fetchKeyEducation(): Promise<KeyEducationResponse> {
  const response = await fetch(`${API_BASE_URL}/keys/guide`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Key education guide could not be loaded."));
  }

  return response.json() as Promise<KeyEducationResponse>;
}

export async function fetchScenarioLifecycle(
  runId: string,
  labSessionId: string
): Promise<TransactionLifecycleTimeline> {
  const query = new URLSearchParams({ lab_session_id: labSessionId });
  const response = await fetch(
    `${API_BASE_URL}/scenario-runs/${encodeURIComponent(runId)}/lifecycle?${query.toString()}`,
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error(await extractApiError(response, "The scenario lifecycle could not be loaded."));
  }
  return response.json() as Promise<TransactionLifecycleTimeline>;
}

export async function runDemoMode(
  walletName: string,
  freshWallet: boolean,
  mineBlocks: number,
  sendAmountBtc: number,
  includeScriptSample: boolean
): Promise<DemoRunResponse> {
  return postJson<DemoRunResponse>(
    "/demo/run",
    {
      wallet_name: walletName,
      fresh_wallet: freshWallet,
      mine_blocks: mineBlocks,
      send_amount_btc: sendAmountBtc,
      include_script_sample: includeScriptSample
    },
    "Demo Mode could not be completed."
  );
}

export async function fetchBlock(query: string): Promise<BlockResponse> {
  const response = await fetch(`${API_BASE_URL}/blocks/${encodeURIComponent(query)}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "That block could not be loaded."));
  }

  return response.json() as Promise<BlockResponse>;
}

export async function fetchTransaction(txid: string): Promise<TransactionResponse> {
  const response = await fetch(`${API_BASE_URL}/transactions/${encodeURIComponent(txid)}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "That transaction could not be loaded."));
  }

  return response.json() as Promise<TransactionResponse>;
}

export async function fetchTransactionPolicy(txid: string): Promise<TransactionPolicyResponse> {
  const response = await fetch(`${API_BASE_URL}/transactions/${encodeURIComponent(txid)}/policy`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Transaction policy data could not be loaded."));
  }

  return response.json() as Promise<TransactionPolicyResponse>;
}

export async function bumpRbfTransaction(
  walletName: string,
  txid: string,
  feeRateSatVb: number | null,
  confTarget: number | null
): Promise<RbfBumpResponse> {
  return postJson<RbfBumpResponse>(
    "/transactions/rbf-bump",
    {
      wallet_name: walletName,
      txid,
      fee_rate_sat_vb: feeRateSatVb,
      conf_target: confTarget
    },
    "RBF fee bump could not be created."
  );
}

export async function createCpfpChild(
  walletName: string,
  parentTxid: string,
  parentVout: number,
  destinationAddress: string,
  amountBtc: number,
  feeRateSatVb: number | null,
  broadcast: boolean
): Promise<CpfpChildResponse> {
  return postJson<CpfpChildResponse>(
    "/transactions/cpfp-child",
    {
      wallet_name: walletName,
      parent_txid: parentTxid,
      parent_vout: parentVout,
      destination_address: destinationAddress,
      amount_btc: amountBtc,
      fee_rate_sat_vb: feeRateSatVb,
      broadcast
    },
    "CPFP child transaction could not be created."
  );
}

export async function createMultisig(
  walletName: string,
  requiredSignatures: number,
  signerCount: number,
  addressType: string
): Promise<MultisigCreateResponse> {
  return postJson<MultisigCreateResponse>(
    "/multisig/create",
    {
      wallet_name: walletName,
      required_signatures: requiredSignatures,
      signer_count: signerCount,
      address_type: addressType
    },
    "Multisig address could not be created."
  );
}

export async function fundMultisig(
  walletName: string,
  multisigAddress: string,
  amountBtc: number,
  mineConfirmation: boolean
): Promise<MultisigFundResponse> {
  return postJson<MultisigFundResponse>(
    "/multisig/fund",
    {
      wallet_name: walletName,
      multisig_address: multisigAddress,
      amount_btc: amountBtc,
      mine_confirmation: mineConfirmation
    },
    "Multisig address could not be funded."
  );
}

export async function spendMultisigPsbt(
  walletName: string,
  multisigAddress: string,
  destinationAddress: string,
  amountBtc: number,
  extract: boolean
): Promise<MultisigSpendResponse> {
  return postJson<MultisigSpendResponse>(
    "/multisig/spend-psbt",
    {
      wallet_name: walletName,
      multisig_address: multisigAddress,
      destination_address: destinationAddress,
      amount_btc: amountBtc,
      extract
    },
    "Multisig PSBT spend could not be created."
  );
}

export async function createLocktimeTransaction(
  walletName: string,
  destinationAddress: string,
  amountBtc: number,
  locktime: number,
  sequence: number
): Promise<LocktimeTransactionResponse> {
  return postJson<LocktimeTransactionResponse>(
    "/timelocks/transaction",
    {
      wallet_name: walletName,
      destination_address: destinationAddress,
      amount_btc: amountBtc,
      locktime,
      sequence
    },
    "Locktime transaction could not be created."
  );
}

export async function createTimelockScriptTemplate(
  mode: string,
  value: number,
  pubkeyHex: string
): Promise<TimelockScriptResponse> {
  return postJson<TimelockScriptResponse>(
    "/timelocks/script-template",
    {
      mode,
      value,
      pubkey_hex: pubkeyHex
    },
    "Timelock script template could not be created."
  );
}

export async function buildRegtestTransaction(
  walletName: string,
  address: string,
  amountBtc: number
): Promise<RegtestTransactionBuildResponse> {
  return postJson<RegtestTransactionBuildResponse>(
    "/transactions/create-regtest",
    {
      wallet_name: walletName,
      address,
      amount_btc: amountBtc
    },
    "Regtest transaction could not be built."
  );
}

export async function sendRegtestTransaction(
  walletName: string,
  address: string,
  amountBtc: number,
  mineConfirmation: boolean
): Promise<RegtestTransactionSendResponse> {
  return postJson<RegtestTransactionSendResponse>(
    "/transactions/send-regtest",
    {
      wallet_name: walletName,
      address,
      amount_btc: amountBtc,
      mine_confirmation: mineConfirmation
    },
    "Regtest transaction could not be sent."
  );
}

export async function fetchMempool(): Promise<MempoolSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/mempool`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "The mempool summary could not be loaded."));
  }

  return response.json() as Promise<MempoolSummaryResponse>;
}

export async function fetchMempoolEntry(txid: string): Promise<MempoolEntryResponse> {
  const response = await fetch(`${API_BASE_URL}/mempool/${encodeURIComponent(txid)}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "That transaction is not in the mempool."));
  }

  return response.json() as Promise<MempoolEntryResponse>;
}

export async function fetchFees(): Promise<FeeEstimateResponse> {
  const response = await fetch(`${API_BASE_URL}/fees`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Fee estimates could not be loaded."));
  }

  return response.json() as Promise<FeeEstimateResponse>;
}

export async function fetchAddress(address: string): Promise<AddressResponse> {
  const response = await fetch(`${API_BASE_URL}/addresses/${encodeURIComponent(address)}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "That address could not be loaded."));
  }

  return response.json() as Promise<AddressResponse>;
}

export async function scanAddressIndex(address: string, startHeight: number, endHeight: number): Promise<AddressIndexScanResponse> {
  return postJson<AddressIndexScanResponse>(
    "/index/scan-address",
    {
      address,
      start_height: startHeight,
      end_height: endHeight
    },
    "Address index scan could not be completed."
  );
}

export async function analyzeDescriptor(
  descriptor: string,
  deriveStart: number | null,
  deriveEnd: number | null
): Promise<DescriptorAnalyzeResponse> {
  return postJson<DescriptorAnalyzeResponse>(
    "/descriptors/analyze",
    {
      descriptor,
      derive_start: deriveStart,
      derive_end: deriveEnd
    },
    "Descriptor could not be analyzed."
  );
}

export async function fetchWalletDescriptors(walletName: string): Promise<WalletDescriptorsResponse> {
  const response = await fetch(`${API_BASE_URL}/descriptors/wallet/${encodeURIComponent(walletName)}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Wallet descriptors could not be loaded."));
  }

  return response.json() as Promise<WalletDescriptorsResponse>;
}

export async function fetchWallets(): Promise<WalletSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/wallets`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Wallets could not be loaded."));
  }

  return response.json() as Promise<WalletSummaryResponse>;
}

export async function createWallet(walletName: string): Promise<WalletActionResponse> {
  return postJson<WalletActionResponse>("/wallets/create", { wallet_name: walletName }, "Wallet could not be created.");
}

export async function loadWallet(walletName: string): Promise<WalletActionResponse> {
  return postJson<WalletActionResponse>("/wallets/load", { wallet_name: walletName }, "Wallet could not be loaded.");
}

export async function fetchWalletBalance(walletName: string): Promise<WalletBalanceResponse> {
  const response = await fetch(`${API_BASE_URL}/wallets/${encodeURIComponent(walletName)}/balance`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Wallet balance could not be loaded."));
  }

  return response.json() as Promise<WalletBalanceResponse>;
}

export async function getNewWalletAddress(walletName: string, label: string, addressType: string): Promise<WalletAddressResponse> {
  return postJson<WalletAddressResponse>(
    `/wallets/${encodeURIComponent(walletName)}/address`,
    { label, address_type: addressType },
    "A new wallet address could not be generated."
  );
}

export async function fetchWalletUtxos(walletName: string): Promise<WalletUtxosResponse> {
  const response = await fetch(`${API_BASE_URL}/wallets/${encodeURIComponent(walletName)}/utxos`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Wallet UTXOs could not be loaded."));
  }

  return response.json() as Promise<WalletUtxosResponse>;
}

export async function fetchWalletTransactions(walletName: string, count = 20): Promise<WalletTransactionsResponse> {
  const response = await fetch(`${API_BASE_URL}/wallets/${encodeURIComponent(walletName)}/transactions?count=${count}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Wallet transactions could not be loaded."));
  }

  return response.json() as Promise<WalletTransactionsResponse>;
}

export async function mineRegtestBlocks(blocks: number, walletName: string, address: string): Promise<RegtestMineResponse> {
  return postJson<RegtestMineResponse>(
    "/regtest/mine",
    {
      blocks,
      wallet_name: walletName || null,
      address: address || null
    },
    "Regtest blocks could not be mined."
  );
}

export async function sendRegtestFaucet(
  walletName: string,
  address: string,
  amountBtc: number,
  mineConfirmation: boolean
): Promise<RegtestFaucetResponse> {
  return postJson<RegtestFaucetResponse>(
    "/regtest/faucet",
    {
      wallet_name: walletName,
      address,
      amount_btc: amountBtc,
      mine_confirmation: mineConfirmation
    },
    "Regtest faucet transaction could not be sent."
  );
}

export async function decodeScript(scriptHex: string): Promise<DecodeScriptResponse> {
  return postJson<DecodeScriptResponse>(
    "/scripts/decode",
    { script_hex: scriptHex },
    "Script hex could not be decoded."
  );
}

export async function createScriptTemplate(
  template: string,
  pubkeyHex: string,
  fallbackPubkeyHex: string,
  pubkeyHashHex: string,
  hashHex: string
): Promise<ScriptTemplateResponse> {
  return postJson<ScriptTemplateResponse>(
    "/scripts/template",
    {
      template,
      pubkey_hex: pubkeyHex || null,
      fallback_pubkey_hex: fallbackPubkeyHex || null,
      pubkey_hash_hex: pubkeyHashHex || null,
      hash_hex: hashHex || null
    },
    "Script template could not be generated."
  );
}

export async function testScriptSpend(transactionHex: string): Promise<ScriptTestResponse> {
  return postJson<ScriptTestResponse>(
    "/scripts/test-spend",
    { transaction_hex: transactionHex },
    "Transaction could not be tested against mempool policy."
  );
}

export async function createOpReturnTransaction(
  walletName: string,
  data: string,
  dataFormat: string,
  destinationAddress: string,
  amountBtc: number | null,
  broadcast: boolean,
  mineConfirmation: boolean
): Promise<OpReturnTransactionResponse> {
  return postJson<OpReturnTransactionResponse>(
    "/scripts/create-op-return",
    {
      wallet_name: walletName,
      data,
      data_format: dataFormat,
      destination_address: destinationAddress || null,
      amount_btc: amountBtc,
      broadcast,
      mine_confirmation: mineConfirmation
    },
    "OP_RETURN transaction could not be created."
  );
}

export async function inspectTaproot(address: string, scriptHex: string): Promise<TaprootInspectResponse> {
  return postJson<TaprootInspectResponse>(
    "/taproot/inspect",
    {
      address: address || null,
      script_hex: scriptHex || null
    },
    "Taproot data could not be inspected."
  );
}

export async function createPsbt(walletName: string, recipientAddress: string, amountBtc: number): Promise<PsbtCreateResponse> {
  return postJson<PsbtCreateResponse>(
    "/psbt/create",
    {
      wallet_name: walletName,
      recipient_address: recipientAddress,
      amount_btc: amountBtc
    },
    "PSBT could not be created."
  );
}

export async function decodePsbt(psbt: string): Promise<PsbtDecodeResponse> {
  return postJson<PsbtDecodeResponse>("/psbt/decode", { psbt }, "PSBT could not be decoded.");
}

export async function processPsbt(walletName: string, psbt: string, sign: boolean): Promise<PsbtProcessResponse> {
  return postJson<PsbtProcessResponse>(
    "/psbt/wallet-process",
    {
      wallet_name: walletName,
      psbt,
      sign
    },
    "PSBT could not be processed by the wallet."
  );
}

export async function finalizePsbt(psbt: string, extract: boolean): Promise<PsbtFinalizeResponse> {
  return postJson<PsbtFinalizeResponse>("/psbt/finalize", { psbt, extract }, "PSBT could not be finalized.");
}

export async function fetchRpcMethods(): Promise<RpcMethodsResponse> {
  const response = await fetch(`${API_BASE_URL}/rpc/methods`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "RPC method catalog could not be loaded."));
  }

  return response.json() as Promise<RpcMethodsResponse>;
}

export async function executeRpc(method: string, params: unknown[] | Record<string, unknown> | null): Promise<RpcExecuteResponse> {
  return postJson<RpcExecuteResponse>("/rpc/execute", { method, params }, "RPC method could not be executed.");
}

export async function fetchLearningConcepts(): Promise<LearningConceptsResponse> {
  const response = await fetch(`${API_BASE_URL}/learn/concepts`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "Learning concepts could not be loaded."));
  }

  return response.json() as Promise<LearningConceptsResponse>;
}

export async function fetchLearningRpcMethods(): Promise<LearningRpcMethodsResponse> {
  const response = await fetch(`${API_BASE_URL}/learn/rpc-methods`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, "RPC learning reference could not be loaded."));
  }

  return response.json() as Promise<LearningRpcMethodsResponse>;
}

export async function fetchCurriculum(): Promise<CurriculumResponse> {
  const response = await fetch(`${API_BASE_URL}/learn/curriculum`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await extractApiError(response, "The curriculum mapping could not be loaded."));
  }
  return response.json() as Promise<CurriculumResponse>;
}

export async function fetchChallenges(): Promise<ChallengeCatalogResponse> {
  const response = await fetch(`${API_BASE_URL}/learn/challenges`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await extractApiError(response, "Challenge Mode could not be loaded."));
  }
  return response.json() as Promise<ChallengeCatalogResponse>;
}

export async function fetchChallengeHint(challengeId: string, level: number): Promise<ChallengeHint> {
  const response = await fetch(
    `${API_BASE_URL}/learn/challenges/${encodeURIComponent(challengeId)}/hints/${level}`,
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error(await extractApiError(response, "The next challenge hint could not be loaded."));
  }
  return response.json() as Promise<ChallengeHint>;
}

export async function verifyChallenge(
  challengeId: string,
  runId: string,
  labSessionId: string
): Promise<ChallengeVerificationResult> {
  return postJson<ChallengeVerificationResult>(
    `/learn/challenges/${encodeURIComponent(challengeId)}/verify`,
    { run_id: runId, lab_session_id: labSessionId },
    "The challenge result could not be verified."
  );
}

async function postJson<T>(path: string, body: Record<string, unknown>, fallback: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (isMutationPath(path) && LOCAL_ACCESS_TOKEN) {
    headers["X-BitScope-Token"] = LOCAL_ACCESS_TOKEN;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractApiError(response, fallback));
  }

  return response.json() as Promise<T>;
}

function isMutationPath(path: string): boolean {
  return MUTATION_PATHS.has(path) || /^\/wallets\/[^/]+\/address$/.test(path);
}

async function extractApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as Partial<ApiError>;
    const message = payload.message ?? fallback;
    const details = formatApiDetails(payload.details);
    return details ? `${message} ${details}` : message;
  } catch {
    return fallback;
  }
}

function formatApiDetails(details: Record<string, unknown> | undefined): string {
  if (!details) {
    return "";
  }
  const allowedKeys = [
    "wallet_name",
    "trusted_btc",
    "immature_btc",
    "requested_btc",
    "fee_headroom_btc",
    "required_btc",
    "minimum_coinbase_confirmations",
    "address",
    "rpc_method",
    "rpc_code"
  ];
  const parts = allowedKeys
    .filter((key) => details[key] !== undefined && details[key] !== null)
    .map((key) => `${key}: ${String(details[key])}`);
  return parts.length ? `Details: ${parts.join(", ")}.` : "";
}
