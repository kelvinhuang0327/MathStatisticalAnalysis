# frozen_string_literal: true
# Loaded with -r around the original, byte-identical launcher. No skill edits.
require 'json'
require 'time'
require 'fileutils'
require 'tmpdir'
require 'open3'
require 'rbconfig'

module Ac10Observer
  CONFIG = JSON.parse(File.read(File.join(__dir__, 'config.json')))
  LOG = File.join(__dir__, "ruby-#{Process.pid}.jsonl")
  RAW_OPEN = File.method(:open)

  def self.emit(operation, fields = {})
    return if Thread.current[:ac10_observer_busy]
    Thread.current[:ac10_observer_busy] = true
    begin
      event = {'utc' => Time.now.utc.iso8601(9), 'pid' => Process.pid, 'ppid' => Process.ppid,
               'pgid' => Process.getpgrp, 'role' => 'ruby-launcher', 'operation' => operation}.merge(fields)
      RAW_OPEN.call(LOG, File::WRONLY | File::CREAT | File::APPEND, 0o600) do |f|
        f.syswrite(JSON.generate(event) + "\n")
        f.fsync
      end
    ensure
      Thread.current[:ac10_observer_busy] = false
    end
  end

  def self.path(value)
    value.respond_to?(:to_path) ? File.expand_path(value.to_path) : File.expand_path(value.to_s)
  end

  def self.writable?(mode)
    mode.is_a?(Integer) ? (mode & (File::WRONLY | File::RDWR | File::CREAT | File::TRUNC | File::APPEND)) != 0 : mode.to_s.match?(/[wax+]/)
  end
end

module Ac10FileObserver
  def open(*args, &block)
    return super unless Ac10Observer.writable?(args[1])
    target = Ac10Observer.path(args[0])
    Ac10Observer.emit('file-open-request', 'path' => target, 'mode' => args[1])
    begin
      result = super
      Ac10Observer.emit('file-open-return', 'path' => target, 'result' => 'SUCCESS')
      result
    rescue StandardError => error
      Ac10Observer.emit('file-open-return', 'path' => target, 'result' => error.class.name)
      raise
    end
  end

  def rename(from, to)
    result = super
    Ac10Observer.emit('file-rename', 'from' => Ac10Observer.path(from), 'to' => Ac10Observer.path(to), 'result' => result)
    result
  end

  def chmod(mode, *paths)
    result = super
    Ac10Observer.emit('file-chmod', 'paths' => paths.map { |p| Ac10Observer.path(p) }, 'mode' => mode, 'result' => result)
    result
  end

  def unlink(*paths)
    result = super
    Ac10Observer.emit('file-unlink', 'paths' => paths.map { |p| Ac10Observer.path(p) }, 'result' => result)
    result
  end
end

module Ac10DirObserver
  def mkdir(path, *args)
    result = super
    Ac10Observer.emit('directory-create', 'path' => Ac10Observer.path(path), 'result' => result)
    result
  end

  def mktmpdir(prefix = nil, *args, &block)
    if prefix == 'gate-launch-' && args[0] == '/private/tmp'
      Ac10Observer.emit('temporary-parent-binding', 'requested' => args[0], 'effective' => Ac10Observer::CONFIG['runtime_parent'])
      args[0] = Ac10Observer::CONFIG['runtime_parent']
    end
    super(prefix, *args, &block)
  end
end

module Ac10IOObserver
  def write(*args)
    count = super
    Ac10Observer.emit('io-write', 'path' => Ac10Observer.path(path), 'bytes' => count) if respond_to?(:path)
    count
  end

  def syswrite(*args)
    count = super
    Ac10Observer.emit('io-syswrite', 'path' => Ac10Observer.path(path), 'bytes' => count) if respond_to?(:path)
    count
  end
end

module Ac10SpawnObserver
  def spawn(*args)
    child = super
    # Environment hashes and their contents are deliberately not serialized.
    Ac10Observer.emit('process-spawn', 'child_pid' => child,
                     'argv' => args.select { |a| a.is_a?(String) },
                     'executable_argv0' => args.find { |a| a.is_a?(Array) },
                     'cwd' => args.last.is_a?(Hash) ? args.last[:chdir] : nil)
    child
  end
end

File.singleton_class.prepend(Ac10FileObserver)
Dir.singleton_class.prepend(Ac10DirObserver)
IO.prepend(Ac10IOObserver)
Kernel.prepend(Ac10SpawnObserver)
Process.singleton_class.prepend(Ac10SpawnObserver)
Ac10Observer.emit('observer-start', 'executable' => RbConfig.ruby, 'argv' => ARGV,
                  'observer_path' => __FILE__, 'observer_log' => Ac10Observer::LOG)

# An attempted file in this task's new .git proves kernel write denial without
# attempting to write any existing source ref or product file.
probe = File.join(Ac10Observer::CONFIG['isolated_repo'], '.git', 'ac10-ruby-write-denial-probe')
begin
  File.open(probe, File::WRONLY | File::CREAT | File::EXCL, 0o600) { |f| f.write('unexpected') }
  Ac10Observer.emit('sandbox-write-denial-FAILED', 'path' => probe)
  exit 126
rescue Errno::EPERM, Errno::EACCES => error
  Ac10Observer.emit('sandbox-write-denied', 'path' => probe, 'error' => error.class.name, 'exists' => File.exist?(probe))
end
