# frozen_string_literal: true
require 'json'
require 'time'
require 'tmpdir'
require 'open3'
require 'rbconfig'

module R3GateObserver
  ROOT = '/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_E440_EXACT_TREE_FULL_GATE_R3_APPEND_R1'
  EXTERNAL = '/private/tmp/mathstat-e440-full-gate-r3-repo'
  SOURCE = '/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_ADV11_DESCENDANT_STABLE_CONTEXT_R1'
  PYTHON = '/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python'
  RAW_OPEN = File.method(:open)
  RUN_TAG = (ARGV.each_cons(2).find { |a,b| a == '--execution-id' } || [nil,nil])[1] || 'unknown'
  LOG = File.join(ROOT, "ruby-observer-#{RUN_TAG}-#{Process.pid}.jsonl")
  GIT_TRACE = File.join(ROOT, "git-ruby-#{RUN_TAG}-#{Process.pid}.jsonl")
  THREAD_GUARD = :r3_gate_observer_busy

  def self.emit(operation, fields = {})
    return if Thread.current[THREAD_GUARD]
    Thread.current[THREAD_GUARD] = true
    begin
      event = {'time_ns'=>Process.clock_gettime(Process::CLOCK_REALTIME, :nanosecond),
               'pid'=>Process.pid,'ppid'=>Process.ppid,'pgid'=>Process.getpgrp,
               'run_tag'=>RUN_TAG,'role'=>'protected-launcher-ruby','operation'=>operation}.merge(fields)
      RAW_OPEN.call(LOG, File::WRONLY|File::CREAT|File::APPEND, 0o600) do |f|
        f.syswrite(JSON.generate(event)+"\n")
        f.fsync
      end
    ensure
      Thread.current[THREAD_GUARD] = false
    end
  end

  def self.path(v)
    v.respond_to?(:to_path) ? File.expand_path(v.to_path) : File.expand_path(v.to_s)
  rescue StandardError
    v.to_s
  end

  def self.writable?(mode)
    if mode.is_a?(Hash)
      return writable?(mode['mode'] || mode[:mode])
    end
    mode.is_a?(Integer) ? (mode & (File::WRONLY|File::RDWR|File::CREAT|File::TRUNC|File::APPEND)) != 0 : mode.to_s.match?(/[wax+]/)
  end

  def self.flat(args)
    args.flat_map { |x| x.is_a?(Array) ? x.grep(String) : (x.is_a?(String) ? [x] : []) }
  end

  def self.cwd(args)
    args.reverse_each do |x|
      return x[:chdir] || x['chdir'] if x.is_a?(Hash) && (x.key?(:chdir) || x.key?('chdir'))
    end
    nil
  end

  def self.lock_fd
    return {'env_fd'=>'NOT_10','open'=>false} unless ENV['FABLE_PROTECTED_RUN_LOCK_FD'] == '10'
    io=IO.for_fd(10, autoclose:false); s=io.stat
    {'env_fd'=>'10','open'=>true,'regular_file'=>s.file?,'dev'=>s.dev,'ino'=>s.ino,'mode'=>format('%04o',s.mode & 0o777)}
  rescue StandardError => e
    {'env_fd'=>'10','open'=>false,'error'=>e.class.name}
  end
end

module R3GateFileObserver
  def open(*args, &block)
    return super unless R3GateObserver.writable?(args[1])
    path=R3GateObserver.path(args[0]); R3GateObserver.emit('file-write-request', 'path'=>path, 'mode'=>args[1].to_s)
    begin
      out=super; R3GateObserver.emit('file-open-result','path'=>path,'result'=>'SUCCESS'); out
    rescue StandardError=>e
      R3GateObserver.emit('file-open-result','path'=>path,'result'=>e.class.name); raise
    end
  end
  def rename(a,b)
    out=super; R3GateObserver.emit('file-rename','from'=>R3GateObserver.path(a),'to'=>R3GateObserver.path(b)); out
  end
  def unlink(*a)
    out=super; R3GateObserver.emit('file-unlink','paths'=>a.map{|x|R3GateObserver.path(x)}); out
  end
  def chmod(mode,*a)
    out=super; R3GateObserver.emit('file-chmod','paths'=>a.map{|x|R3GateObserver.path(x)},'mode'=>mode); out
  end
end
module R3GateDirObserver
  def mkdir(path,*a)
    out=super; R3GateObserver.emit('directory-create','path'=>R3GateObserver.path(path),'mode'=>a.first); out
  end
  def mktmpdir(prefix=nil,*a,&block)
    out=super
    actual=block ? nil : out
    R3GateObserver.emit('temporary-directory','prefix'=>prefix,'path'=>actual || 'block-managed')
    out
  end
end
module R3GateSpawnObserver
  def spawn(*args)
    pid=super
    R3GateObserver.emit('process-spawn','child_pid'=>pid,'argv'=>R3GateObserver.flat(args),'cwd'=>R3GateObserver.cwd(args))
    pid
  end
end
module R3GateOpen3Observer
  def capture2(*args, &block)
    flat=R3GateObserver.flat(args)
    if flat.first == 'git' || flat.first == '/usr/bin/git'
      if args.first.is_a?(Hash)
        copy=args.first.dup; args=args.dup; args[0]=copy
      else
        copy={}; args=args.dup; args.unshift(copy)
      end
      copy['GIT_TRACE2_EVENT']=R3GateObserver::GIT_TRACE
      copy['GIT_OPTIONAL_LOCKS']='0'; copy['GIT_NO_LAZY_FETCH']='1'
      R3GateObserver.emit('git-query-request','argv'=>flat,'trace2_path'=>R3GateObserver::GIT_TRACE)
    end
    super(*args, &block)
  end

  def popen3(*args, &block)
    args=args.dup
    env_index=args.first.is_a?(Hash) ? 0 : nil
    flat=R3GateObserver.flat(args)
    if env_index && flat.first == R3GateObserver::PYTHON
      env=args[env_index].dup
      role=flat.each_cons(2).any?{|a,b|a=='-m' && b=='pytest'} ? 'pytest' : (flat.include?('-c') ? 'metadata-probe' : nil)
      if role
        current=env['PYTHONPATH'].to_s.split(File::PATH_SEPARATOR)
        observer=File.join(R3GateObserver::ROOT,'python-observer')
        env['PYTHONPATH']=([observer]+current.reject{|x|x==observer}).join(File::PATH_SEPARATOR)
        env['GIT_TRACE2_EVENT']=File.join(R3GateObserver::ROOT,"git-python-#{R3GateObserver::RUN_TAG}.jsonl")
        env['FABLE_R3_OBSERVER_ROLE']=role
        env['FABLE_R3_RUN_TAG']=R3GateObserver::RUN_TAG
        env['FABLE_R3_OBSERVER_ROOT_PID']=Process.pid.to_s
        added=['PYTHONPATH observer prefix','GIT_TRACE2_EVENT','FABLE_R3_OBSERVER_ROLE','FABLE_R3_RUN_TAG','FABLE_R3_OBSERVER_ROOT_PID']
        t249_report_path=nil
        if role == 'pytest' && flat.include?('tests/unit/test_b649_t249_collection_isolation_r1.py')
          t249_report_path=File.join(R3GateObserver::ROOT,'t249-02-evidence',"t249-parent-state-#{R3GateObserver::RUN_TAG}.json")
          env['FABLE_R3_T249_PARENT_STATE_REPORT']=t249_report_path
          added += ['FABLE_R3_T249_PARENT_STATE_REPORT']
        end
        args[env_index]=env
        R3GateObserver.emit('python-instrumentation-overlay','role'=>role,'argv'=>flat,
          'added'=>added,'t249_parent_state_path'=>t249_report_path,'observer_path'=>observer)
      end
    end
    if block
      wrapped=proc do |stdin,stdout,stderr,wait_thr|
        R3GateObserver.emit('open3-child-start','child_pid'=>wait_thr.pid,'argv'=>flat,'cwd'=>R3GateObserver.cwd(args))
        begin
          block.call(stdin,stdout,stderr,wait_thr)
        ensure
          R3GateObserver.emit('open3-child-finished','child_pid'=>wait_thr.pid)
        end
      end
      super(*args, &wrapped)
    else
      super(*args, &block)
    end
  end
end

File.singleton_class.prepend(R3GateFileObserver)
Dir.singleton_class.prepend(R3GateDirObserver)
Kernel.prepend(R3GateSpawnObserver)
Process.singleton_class.prepend(R3GateSpawnObserver)
Open3.singleton_class.prepend(R3GateOpen3Observer)

R3GateObserver.emit('observer-start','executable'=>RbConfig.ruby,'argv'=>ARGV,'lock_fd10'=>R3GateObserver.lock_fd,
                    'observer_path'=>__FILE__,'observer_log'=>R3GateObserver::LOG)
raise 'protected lock FD10 was not inherited by launcher process' unless R3GateObserver.lock_fd['open'] && R3GateObserver.lock_fd['regular_file']
