#!/usr/bin/env python3
"""
Main entry point for the Pokemon Agent.
This is a streamlined version that focuses on multiprocess mode only.
"""

import os
import sys
import time
import argparse
import subprocess
import signal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from server.client import run_multiprocess_client


def start_server(args):
    """Start the server process with appropriate arguments"""
    # Use the same Python executable that's running this script
    python_exe = sys.executable
    server_cmd = [python_exe, "-m", "server.app", "--port", str(args.port)]

    # Pass through server-relevant arguments
    if args.record:
        server_cmd.append("--record")

    # Pass emulator speed multiplier
    if args.emulator_speed != 1.0:
        server_cmd.extend(["--emulator-speed", str(args.emulator_speed)])
        print(f"⚡ Passing --emulator-speed {args.emulator_speed} to server")

    if args.load_milestone:
        # Load from a specific milestone checkpoint
        import glob

        # Check if it's a direct path or a milestone name
        if os.path.exists(args.load_milestone) and args.load_milestone.endswith('.state'):
            # Direct path to state file
            milestone_path = args.load_milestone
        else:
            # Milestone name - find the latest checkpoint for this milestone
            checkpoint_pattern = f"checkpoints/milestones/{args.load_milestone}_*.state"
            matching_files = sorted(glob.glob(checkpoint_pattern), reverse=True)

            if matching_files:
                milestone_path = matching_files[0]  # Most recent
            else:
                print(f"⚠️  No checkpoint found for milestone: {args.load_milestone}")
                print(f"   Looking for: {checkpoint_pattern}")
                milestone_path = None

        if milestone_path:
            server_cmd.extend(["--load-state", milestone_path])
            print(f"🎯 Server will load milestone checkpoint: {milestone_path}")
    elif args.load_checkpoint:
        # Auto-load checkpoint.state when --load-checkpoint is used
        checkpoint_state = ".pokeagent_cache/checkpoint.state"
        if os.path.exists(checkpoint_state):
            server_cmd.extend(["--load-state", checkpoint_state])
            # Set environment variable to enable LLM checkpoint loading
            os.environ["LOAD_CHECKPOINT_MODE"] = "true"
            print(f"🔄 Server will load checkpoint: {checkpoint_state}")
            print(f"🔄 LLM metrics will be restored from .pokeagent_cache/checkpoint_llm.txt")
        else:
            print(f"⚠️ Checkpoint file not found: {checkpoint_state}")
    elif args.load_state:
        server_cmd.extend(["--load-state", args.load_state])
    
    # Don't pass --manual to server - server should always run in server mode
    # The --manual flag only affects client behavior
    
    if args.no_ocr:
        server_cmd.append("--no-ocr")
    
    # Server always runs headless - display handled by client
    
    # Start server as subprocess
    try:
        print(f"📋 Server command: {' '.join(server_cmd)}")
        server_process = subprocess.Popen(
            server_cmd,
            universal_newlines=True,
            bufsize=1
        )
        print(f"✅ Server started with PID {server_process.pid}")
        print("⏳ Waiting 3 seconds for server to initialize...")
        time.sleep(3)
        
        return server_process
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None


def start_frame_server(port):
    """Start the lightweight frame server for stream.html visualization"""
    try:
        # Use the same Python executable that's running this script
        python_exe = sys.executable
        frame_cmd = [python_exe, "-m", "server.frame_server", "--port", str(port+1), "--host", "0.0.0.0"]

        # Don't use PIPE for stdout/stderr - let them go to console or devnull
        # Using PIPE can cause deadlocks if buffers fill up
        frame_process = subprocess.Popen(
            frame_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"🖼️  Frame server started with PID {frame_process.pid} on port {port+1}")
        print(f"🎥 Frame server URL: http://localhost:{port+1}")

        # Give it a moment to start
        time.sleep(0.5)

        # Check if it's still running
        if frame_process.poll() is not None:
            print(f"⚠️  Frame server exited immediately with code {frame_process.returncode}")
            return None

        return frame_process
    except Exception as e:
        print(f"⚠️ Could not start frame server: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point for the Pokemon Agent"""
    parser = argparse.ArgumentParser(description="Pokemon Emerald AI Agent")
    
    # Core arguments
    parser.add_argument("--rom", type=str, default="Emerald-GBAdvance/rom.gba", 
                       help="Path to ROM file")
    parser.add_argument("--port", type=int, default=8000, 
                       help="Port for web interface")
    
    # State loading
    parser.add_argument("--load-state", type=str,
                       help="Load a saved state file on startup")
    parser.add_argument("--load-checkpoint", action="store_true",
                       help="Load from checkpoint files")
    parser.add_argument("--load-milestone", type=str,
                       help="Load from a specific milestone checkpoint (e.g., 'INTRO_CUTSCENE_COMPLETE' or path to .state file)")
    
    # Agent configuration
    parser.add_argument("--backend", type=str, default="gemini",
                       help="VLM backend (openai, gemini, local, openrouter, vertex, lmstudio)")
    parser.add_argument("--model-name", type=str, default="gemini-2.5-flash",
                       help="Model name to use")
    parser.add_argument("--vertex-id", type=str,
                       help="Google Cloud project ID for Vertex AI backend (required for --backend vertex)")
    parser.add_argument("--lmstudio-url", type=str, default="http://localhost:1234/v1",
                       help="Base URL for LM Studio API (default: http://localhost:1234/v1)")
    parser.add_argument("--lmstudio-max-tokens", type=int, default=500,
                       help="Max tokens for LM Studio responses (default: 500, lower = faster)")
    parser.add_argument("--lmstudio-timeout", type=int, default=60,
                       help="Timeout in seconds for LM Studio API calls (default: 60)")
    parser.add_argument("--lmstudio-cooldown", type=float, default=25.0,
                       help="Cooldown in seconds between LM Studio API calls (default: 25.0)")
    parser.add_argument("--scaffold", type=str, default="simple",
                       choices=["simple", "react"],
                       help="Agent scaffold: simple (default) or react")
    parser.add_argument("--simple", action="store_true",
                       help="DEPRECATED: Use --scaffold simple instead")
    
    # Operation modes
    parser.add_argument("--headless", action="store_true", 
                       help="Run without pygame display (headless)")
    parser.add_argument("--agent-auto", action="store_true", 
                       help="Agent acts automatically")
    parser.add_argument("--manual", action="store_true", 
                       help="Start in manual mode instead of agent mode")
    
    # Features
    parser.add_argument("--record", action="store_true",
                       help="Record video of the gameplay")
    parser.add_argument("--no-ocr", action="store_true",
                       help="Disable OCR dialogue detection")
    parser.add_argument("--emulator-speed", type=float, default=1.0,
                       help="Emulator speed multiplier (1.0=normal, 2.0=2x, 3.0=3x faster)")

    args = parser.parse_args()

    # Validate vertex backend requirements
    if args.backend == "vertex" and not args.vertex_id:
        parser.error("--vertex-id is required when using --backend vertex")

    print("=" * 60)
    print("🎮 Pokemon Emerald AI Agent")
    print("=" * 60)

    # Display emulator speed if not default
    if args.emulator_speed != 1.0:
        print(f"⚡ Emulator Speed: {args.emulator_speed}x")

    server_process = None
    frame_server_process = None
    
    try:
        # Auto-start server if requested
        if args.agent_auto or args.manual:
            print("\n📡 Starting server process...")
            server_process = start_server(args)
            
            if not server_process:
                print("❌ Failed to start server, exiting...")
                return 1
            
            # Also start frame server for web visualization
            frame_server_process = start_frame_server(args.port)
        else:
            print("\n📋 Manual server mode - start server separately with:")
            print("   python -m server.app --port", args.port)
            if args.load_state:
                print(f"   (Add --load-state {args.load_state} to server command)")
            print("\n⏳ Waiting 3 seconds for manual server startup...")
            time.sleep(3)
        
        # Handle deprecated --simple flag
        if args.simple:
            print("⚠️ --simple is deprecated. Using --scaffold simple")
            args.scaffold = "simple"
        
        # Display configuration
        print("\n🤖 Agent Configuration:")
        print(f"   Backend: {args.backend}")
        print(f"   Model: {args.model_name}")
        scaffold_descriptions = {
            "simple": "Simple mode (direct frame→action)",
            "react": "ReAct agent (Thought→Action→Observation loop)"
        }
        print(f"   Scaffold: {scaffold_descriptions.get(args.scaffold, args.scaffold)}")
        if args.no_ocr:
            print("   OCR: Disabled")
        if args.record:
            print("   Recording: Enabled")
        
        print(f"🎥 Stream View: http://127.0.0.1:{args.port}/stream")

        print("\n🚀 Starting client...")
        print("-" * 60)

        # Run the client
        success = run_multiprocess_client(server_port=args.port, args=args)

        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutdown requested by user")
        return 0
        
    finally:
        # Clean up server processes
        if server_process:
            print("\n📡 Stopping server process...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("   Force killing server...")
                server_process.kill()
        
        if frame_server_process:
            print("🖼️  Stopping frame server...")
            frame_server_process.terminate()
            try:
                frame_server_process.wait(timeout=2)
            except:
                frame_server_process.kill()
        
        print("👋 Goodbye!")


if __name__ == "__main__":
    sys.exit(main())