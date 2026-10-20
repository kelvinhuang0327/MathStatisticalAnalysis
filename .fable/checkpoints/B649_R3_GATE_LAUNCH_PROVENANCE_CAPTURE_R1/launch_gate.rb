#!/usr/bin/env ruby
# frozen_string_literal: true

# Task-local provenance adapter. Terminal capture belongs to the pinned Fable
# implementation; long-running use additionally requires its protected --run.
require 'json'
require 'digest'
require 'fileutils'
require 'tmpdir'
require 'optparse'
require 'open3'
require 'time'

TASK = 'B649_R3_GATE_LAUNCH_PROVENANCE_CAPTURE_R1'
ROOT = '/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/' + TASK
PRIMARY = '/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis'
DEFAULT_SOURCE = '/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_ADV11_DESCENDANT_STABLE_CONTEXT_R1'
DEFAULT_HEAD = 'e440d4298551ce93ef3ea9a9226143784afa3eff'
DEFAULT_TREE = '294cbf6bbe7ee8a8ebad947f397852edc1981b57'
FABLE = '/Users/kelvin/.codex/skills/fable-method/scripts/task_checkpoint.rb'
FABLE_BLOB = '00e2cf4a4f06b0f0a8d8e4be6091a4304e6e2ae4'
JUDGE = PRIMARY + '/.fable/checkpoints/B649_R3_E440_EXACT_TREE_FULL_GATE_R1/judge-report.md'
JUDGE_SHA = '028e60ce4b0290a97c3b140b902157e4eb72eb2d1527f6297710c10a9dc22c68'

def sha(path)
  Digest::SHA256.file(path).hexdigest
end

def utc
  Time.now.utc.iso8601(9)
end

def write_new(path, value)
  File.open(path, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |f|
    f.binmode.write(value)
    f.flush
    f.fsync
  end
  File.open(File.dirname(path)) { |f| f.fsync }
  path
end

def write_json(path, value)
  write_new(path, JSON.pretty_generate(value) + "\n")
end

def git(path, *args)
  out, err, status = Open3.capture3({'GIT_OPTIONAL_LOCKS' => '0', 'GIT_NO_LAZY_FETCH' => '1'},
                                  '/usr/bin/git', '--no-optional-locks', '-C', path, *args)
  raise "read-only Git query failed: #{args.inspect}: #{err}" unless status.success?
  out
end

def outside!(path)
  real = File.realpath(path)
  [PRIMARY, DEFAULT_SOURCE, SOURCE].each do |protected_root|
    raise 'runtime path overlaps protected worktree' if real == protected_root || real.start_with?(protected_root + '/')
  end
  real
end

def directory_info(path)
  stat = File.stat(path)
  {'path' => File.realpath(path), 'mode' => format('%04o', stat.mode & 0o777), 'uid' => stat.uid}
end

def git_identity(path)
  alternates = git(path, 'rev-parse', '--path-format=absolute', '--git-path', 'objects/info/alternates').strip
  {'path' => path, 'head' => git(path, 'rev-parse', 'HEAD').strip,
   'tree' => git(path, 'rev-parse', 'HEAD^{tree}').strip,
   'parents' => git(path, 'show', '-s', '--format=%P', 'HEAD').strip.split,
   'shallow' => git(path, 'rev-parse', '--is-shallow-repository').strip,
   'alternates' => {'path' => alternates, 'exists' => File.exist?(alternates),
                    'sha256' => File.file?(alternates) ? sha(alternates) : nil},
   'git_common_dir' => git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip}
end

def snapshot(run_dir, stage, cwd)
  result = {}
  {'source' => SOURCE, 'primary' => PRIMARY}.each do |name, path|
    refs = git(path, 'for-each-ref', '--sort=refname', '--format=%(refname) %(objectname) %(symref)')
    status = git(path, 'status', '--porcelain=v1', '--untracked-files=all')
    ref_path = write_new(File.join(run_dir, "#{name}-refs-#{stage}.txt"), refs)
    status_path = write_new(File.join(run_dir, "#{name}-status-#{stage}.txt"), status)
    result[name] = {'identity' => git_identity(path), 'refs_path' => ref_path, 'refs_sha256' => sha(ref_path),
                    'refs_count' => refs.lines.count, 'status_path' => status_path, 'status_sha256' => sha(status_path)}
  end
  # A future external test checkout is recorded separately from the protected source.
  out, = Open3.capture3('/usr/bin/git', '--no-optional-locks', '-C', cwd, 'rev-parse', '--show-toplevel')
  result['execution_checkout'] = git_identity(cwd) if out.strip == cwd
  result
end

def differences(before, after)
  before_lines = File.readlines(before)
  after_lines = File.readlines(after)
  {'removed' => before_lines - after_lines, 'added' => after_lines - before_lines}
end

options = {python: PRIMARY + '/.venv/bin/python', kind: 'smoke'}
parser = OptionParser.new do |p|
  p.banner = 'launch_gate.rb --execution-id ID [--kind smoke|pytest] [--cwd EXTERNAL] [--python ABS] -- Python-script-args | pytest-args'
  p.on('--execution-id ID') { |v| options[:id] = v }
  p.on('--kind KIND') { |v| options[:kind] = v }
  p.on('--cwd PATH') { |v| options[:cwd] = v }
  p.on('--python PATH') { |v| options[:python] = v }
  p.on('--source-worktree PATH') { |v| options[:source] = v }
  p.on('--expected-head SHA') { |v| options[:head] = v }
  p.on('--expected-tree SHA') { |v| options[:tree] = v }
end

begin
  parser.parse!(ARGV)
  pins = %i[source head tree]
  raise 'custom source requires all three explicit source/head/tree pins' if pins.any? { |k| options.key?(k) } && !pins.all? { |k| options.key?(k) }
  SOURCE = File.realpath(options.fetch(:source, DEFAULT_SOURCE))
  HEAD = options.fetch(:head, DEFAULT_HEAD)
  TREE = options.fetch(:tree, DEFAULT_TREE)
  raise 'source pins must be full lowercase Git object IDs' unless [HEAD, TREE].all? { |s| s.match?(/\A[0-9a-f]{40}\z/) }
  raise 'source must be the exact Git worktree root' unless git(SOURCE, 'rev-parse', '--show-toplevel').strip == SOURCE
  raise 'execution-id must be a stable path component' unless options[:id].to_s.match?(/\A[A-Za-z0-9][A-Za-z0-9_.-]*\z/)
  raise 'kind must be smoke or pytest' unless %w[smoke pytest].include?(options[:kind])
  raise 'upstream arguments are required' if ARGV.empty?
  raise 'task root binding changed' unless File.realpath(__dir__) == ROOT
  raise 'Python executable must be absolute' unless options[:python].start_with?('/') && File.executable?(options[:python])
  fable_bytes = File.binread(FABLE)
  blob = Digest::SHA1.hexdigest("blob #{fable_bytes.bytesize}\0" + fable_bytes)
  raise 'canonical Fable launcher identity/mode mismatch' unless blob == FABLE_BLOB && (File.stat(FABLE).mode & 0o777) == 0o755
  raise 'old Judge SHA mismatch' unless sha(JUDGE) == JUDGE_SHA
  raise 'source identity mismatch' unless git(SOURCE, 'rev-parse', 'HEAD').strip == HEAD && git(SOURCE, 'rev-parse', 'HEAD^{tree}').strip == TREE
  raise 'source worktree is dirty' unless git(SOURCE, 'status', '--porcelain=v1', '--untracked-files=all').empty?
  inherited_lock = nil
  if options[:kind] == 'pytest'
    # Fail closed for a future long-running run without the canonical outer CLI.
    raise 'pytest requires canonical task_checkpoint.rb --run as outer supervisor' unless ENV['FABLE_PROTECTED_RUN_LOCK_FD'] == '10'
    inherited_lock = IO.for_fd(10, autoclose: false)
    raise 'protected task lock descriptor is not a file' unless inherited_lock.stat.file?
    raise 'pytest cwd must name an external standalone test checkout' unless options[:cwd]
    raise 'runtime path overrides must be supplied by this launcher' if ARGV.any? { |a| a.include?('basetemp') || a.include?('cache_dir') }
  end
  require FABLE
  File.umask(0o077)
  runs = File.join(ROOT, 'runs')
  FileUtils.mkdir_p(runs, mode: 0o700)
  run_dir = File.join(runs, options[:id])
  Dir.mkdir(run_dir, 0o700) # Existing identities are never overwritten or rerun.
  runtime = Dir.mktmpdir('gate-launch-', '/private/tmp')
  outside!(runtime)
  runtime_dirs = %w[appdata basetemp pytest-cache python-cache tmp home cache work]
  runtime_dirs.each { |name| Dir.mkdir(File.join(runtime, name), 0o700) }
  cwd = options[:cwd] ? outside!(options[:cwd]) : File.join(runtime, 'work')
  raise 'external cwd is not a directory' unless File.directory?(cwd)
  if options[:kind] == 'pytest'
    raise 'pytest cwd must be a Git worktree root' unless git(cwd, 'rev-parse', '--show-toplevel').strip == cwd
    raise 'test checkout identity mismatch' unless git(cwd, 'rev-parse', 'HEAD').strip == HEAD && git(cwd, 'rev-parse', 'HEAD^{tree}').strip == TREE
    test_identity = git_identity(cwd)
    outside!(test_identity['git_common_dir'])
    raise 'test checkout must have independent Git metadata' if test_identity['git_common_dir'] == git_identity(SOURCE)['git_common_dir']
    raise 'test checkout must be complete, without alternates' unless test_identity['shallow'] == 'false' && !test_identity['alternates']['exists']
  end
  env = ENV.to_h.transform_values { nil }
  env.merge!('PATH' => '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'LANG' => 'en_US.UTF-8',
             'HOME' => File.join(runtime, 'home'), 'LOTTOLAB_DATA_DIR' => File.join(runtime, 'appdata'),
             'TMPDIR' => File.join(runtime, 'tmp'), 'TMP' => File.join(runtime, 'tmp'), 'TEMP' => File.join(runtime, 'tmp'),
             'PYTHONDONTWRITEBYTECODE' => '1', 'PYTHONPYCACHEPREFIX' => File.join(runtime, 'python-cache'),
             'XDG_CACHE_HOME' => File.join(runtime, 'cache'), 'XDG_DATA_HOME' => File.join(runtime, 'appdata'),
             'UV_CACHE_DIR' => File.join(runtime, 'cache'), 'PIP_CACHE_DIR' => File.join(runtime, 'cache'),
             'GIT_OPTIONAL_LOCKS' => '0', 'GIT_NO_LAZY_FETCH' => '1')
  env['PYTHONPATH'] = File.join(cwd, 'src') if options[:kind] == 'pytest'
  env['FABLE_PROTECTED_RUN_LOCK_FD'] = '10' if inherited_lock
  launch_path = File.join(run_dir, 'launch.json')
  env['GATE_LAUNCH_RECEIPT'] = launch_path
  env['GATE_RUNTIME_ROOT'] = runtime
  env['GATE_BASETEMP'] = File.join(runtime, 'basetemp')
  probe = <<~'PY'
    import sys, json, importlib.metadata as m
    assert sys.version_info[:2] == (3, 13), 'Python 3.13 is required'
    print(json.dumps({'executable':sys.executable,'real_executable':__import__('os').path.realpath(sys.executable),
      'version':sys.version,'pytest':m.version('pytest'),
      'dependencies':sorted([{'name':d.metadata['Name'],'version':d.version} for d in m.distributions()], key=lambda d:(d['name'].lower(), d['version']))}))
  PY
  metadata_out, metadata_err, metadata_status = Open3.capture3(env, options[:python], '-B', '-c', probe, chdir: cwd)
  raise "Python metadata probe failed: #{metadata_err}" unless metadata_status.success?
  metadata = JSON.parse(metadata_out)
  metadata['source_lock_fingerprints'] = %w[uv.lock pyproject.toml .python-version].map do |name|
    path = File.join(SOURCE, name)
    {'path' => path, 'sha256' => sha(path), 'git_blob' => git(SOURCE, 'rev-parse', 'HEAD:' + name).strip}
  end
  dep_path = write_json(File.join(run_dir, 'dependencies.json'), metadata.delete('dependencies'))
  command = [options[:python], '-B']
  command += options[:kind] == 'pytest' ? ['-m', 'pytest', '--basetemp=' + env['GATE_BASETEMP'], '-o', 'cache_dir=' + File.join(runtime, 'pytest-cache'), *ARGV] : ARGV
  before = nil
  launch_sha = nil
  identity = {'repository_path' => PRIMARY, 'worktree_path' => cwd,
              'head' => options[:kind] == 'pytest' ? HEAD : nil, 'tree' => options[:kind] == 'pytest' ? TREE : nil,
              'launcher_path' => FABLE, 'launcher_sha256' => sha(FABLE),
              'runtime_executable' => File.realpath(RbConfig.ruby), 'runtime_version' => RUBY_DESCRIPTION,
              'provenance_launch_path' => launch_path, 'source_head' => HEAD, 'source_tree' => TREE}
  before_spawn = lambda do
    raise 'effective umask mismatch' unless File.umask == 0o077
    runtime_dirs.each do |name|
      info = directory_info(File.join(runtime, name))
      raise 'runtime directory permission/owner mismatch' unless info['mode'] == '0700' && info['uid'] == Process.uid
    end
    before = snapshot(run_dir, 'before', cwd)
    raise 'source changed before spawn' unless before['source']['identity']['head'] == HEAD && before['source']['identity']['tree'] == TREE && File.size(before['source']['status_path']).zero?
    launch = {'schema_version' => 1, 'task_id' => TASK, 'execution_id' => options[:id], 'stage' => 'BEFORE_CHILD_SPAWN',
              'utc_launch_timestamp' => utc, 'argv' => command, 'cwd' => cwd, 'python' => metadata,
              'dependency_manifest' => {'path' => dep_path, 'sha256' => sha(dep_path)},
              'effective_umask' => format('%04o', File.umask), 'appdata' => directory_info(env['LOTTOLAB_DATA_DIR']),
              'runtime_root' => directory_info(runtime), 'basetemp' => directory_info(env['GATE_BASETEMP']),
              'runtime_directories' => runtime_dirs.map { |n| directory_info(File.join(runtime, n)) },
              'environment' => env.reject { |_k, v| v.nil? }, 'environment_policy' => 'cleared inherited environment; only listed task values passed',
              'process' => {'pid' => Process.pid, 'ppid' => Process.ppid, 'pgid' => Process.getpgrp,
                            'runtime_executable' => File.realpath(RbConfig.ruby), 'runtime_version' => RUBY_DESCRIPTION},
              'source_snapshots' => before, 'old_judge_sha256' => sha(JUDGE),
              'adapter_path' => File.realpath(__FILE__), 'adapter_sha256' => sha(__FILE__),
              'canonical_launcher_path' => FABLE, 'canonical_launcher_blob' => blob, 'canonical_launcher_sha256' => sha(FABLE),
              'protection' => inherited_lock ? 'CANONICAL_OUTER_LOCK_INHERITED' : 'SHORT_SMOKE_ONLY; no ExecutionRecord claimed'}
    write_json(launch_path, launch)
    launch_sha = sha(launch_path)
    raise 'launch receipt readback mismatch' unless JSON.parse(File.read(launch_path)) == launch
    # This callback returns only after persistent write, file+directory fsync,
    # and readback. Fable invokes Open3.popen3 only after this callback returns.
    env['GATE_LAUNCH_SHA256'] = launch_sha
    identity['provenance_launch_sha256'] = launch_sha
  end
  capture_path = File.join(run_dir, 'capture.json')
  capture = DurableCommandCapture.run_and_capture(command, file_path: capture_path, chdir: cwd,
    before_spawn: before_spawn, child_env: env, inherited_lock: inherited_lock, execution_identity: identity) do |terminal|
    # The formal Fable schema and original streams/exit are preserved verbatim.
    File.open(capture_path) { |f| f.fsync }
    File.open(run_dir) { |f| f.fsync }
    stdout_path = write_new(File.join(run_dir, 'stdout.txt'), terminal.stdout)
    stderr_path = write_new(File.join(run_dir, 'stderr.txt'), terminal.stderr)
    after = snapshot(run_dir, 'after', cwd)
    changes = differences(before['source']['refs_path'], after['source']['refs_path'])
    status_changes = differences(before['source']['status_path'], after['source']['status_path'])
    runtime_manifest = Dir.glob(File.join(runtime, '**', '*'), File::FNM_DOTMATCH).reject { |p| %w[. ..].include?(File.basename(p)) }.sort.map do |p|
      info = {'path' => p, 'mode' => format('%04o', File.lstat(p).mode & 0o777), 'type' => File.directory?(p) ? 'directory' : 'file'}
      info['sha256'] = sha(p) if File.file?(p) && !File.symlink?(p)
      info
    end
    end_receipt = {'schema_version' => 1, 'task_id' => TASK, 'execution_id' => options[:id],
      'utc_end_timestamp' => utc, 'started_at' => terminal.started_at, 'ended_at' => terminal.ended_at,
      'exit_status' => terminal.exit_status, 'launch_path' => launch_path, 'launch_sha256' => launch_sha,
      'capture_path' => capture_path, 'capture_sha256' => sha(capture_path),
      'stdout' => {'path' => stdout_path, 'sha256' => sha(stdout_path), 'bytes' => File.size(stdout_path)},
      'stderr' => {'path' => stderr_path, 'sha256' => sha(stderr_path), 'bytes' => File.size(stderr_path)},
      'source_snapshots' => after, 'source_refs_diff' => changes, 'source_status_diff' => status_changes,
      'refs_attribution' => changes.values.all?(&:empty?) ? 'NO_OBSERVED_DRIFT' : 'UNKNOWN',
      'attribution_limit' => 'Endpoint observations cannot identify an actor or exclude transient ref changes between snapshots.',
      'old_judge_sha256' => sha(JUDGE), 'runtime_manifest' => runtime_manifest,
      'write_accounting' => {'adapter_persistent_root' => run_dir, 'created_runtime_root' => runtime,
         'adapter_actions' => ['create exclusive run directory', 'create exclusive external runtime directories',
                               'write dependency manifest, before/after snapshots, launch and end receipts',
                               'invoke pinned Fable capture writer; persist original stdout and stderr'],
         'child_writes' => options[:kind] == 'smoke' ? 'observed by controlled smoke; see stdout and runtime manifest' : 'NOT_VERIFIED: requires next Gate task write accounting',
         'deleted_paths' => [], 'git_mutation_commands' => [], 'remote_commands' => [],
         'limit' => 'This adapter records its own writes and endpoint manifests; it is not a filesystem or OS write sandbox.'}}
    end_path = write_json(File.join(run_dir, 'end.json'), end_receipt)
    files = Dir.children(run_dir).map { |n| File.join(run_dir, n) }.select { |p| File.file?(p) }.sort
    write_new(File.join(run_dir, 'SHA256SUMS'), files.map { |p| sha(p) + '  ' + File.basename(p) + "\n" }.join)
    raise 'end receipt readback mismatch' unless JSON.parse(File.read(end_path)) == end_receipt
    $stdout.binmode.write(terminal.stdout)
    $stderr.binmode.write(terminal.stderr)
    $stdout.flush
    $stderr.flush
  end
  signal = capture.wrapper_signal || (capture.exit_status.to_s[/\ASIGNALED:(\d+)\z/, 1]&.to_i)
  if signal
    Signal.trap(signal, 'DEFAULT')
    Process.kill(signal, Process.pid)
  end
  exit capture.exit_status
rescue StandardError => error
  warn "GATE_LAUNCH_FAILED: #{error.class}: #{error.message}"
  # An existing run directory is retained on failure; do not rotate IDs to retry.
  exit 125
end
