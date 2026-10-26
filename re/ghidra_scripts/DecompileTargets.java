// Decompiles selected functions of the current program without whole-program auto-analysis.
// Meant for a 150 MB shipping executable where full analysis takes hours: functions are created on
// demand at the given entry points (taken from .pdata or UFunction exec pointers).
//
// Script args: out <dir> [depth <n>] <entryVA>... [dis:<VA>:<count>]...
//   depth n  also decompiles direct callees n levels deep (exec thunk -> _Implementation)
//   dis:...  dumps <count> instructions starting at <VA>
// "out=<dir>" also works when the arguments do not pass through cmd.exe, which splits on '='.
//@category RonComp

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;

public class DecompileTargets extends GhidraScript {

    private DecompInterface decompiler;
    private File outDir;
    private final Set<Address> done = new HashSet<>();

    @Override
    public void run() throws Exception {
        int depth = 0;
        List<String> targets = new ArrayList<>();
        String[] args = getScriptArgs();
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            if (arg.startsWith("out=")) {
                outDir = new File(arg.substring(4));
            }
            else if (arg.equals("out") && i + 1 < args.length) {
                outDir = new File(args[++i]);
            }
            else if (arg.startsWith("depth=")) {
                depth = Integer.parseInt(arg.substring(6));
            }
            else if (arg.equals("depth") && i + 1 < args.length) {
                depth = Integer.parseInt(args[++i]);
            }
            else {
                targets.add(arg);
            }
        }
        if (outDir == null) {
            throw new IllegalArgumentException("missing out=<dir>");
        }
        outDir.mkdirs();

        decompiler = new DecompInterface();
        decompiler.toggleCCode(true);
        decompiler.openProgram(currentProgram);
        try {
            for (String target : targets) {
                if (target.startsWith("dis:")) {
                    String[] parts = target.split(":");
                    dumpDisassembly(toAddr(parts[1]), Integer.parseInt(parts[2]));
                }
                else {
                    decompileTree(toAddr(target), depth);
                }
            }
        }
        finally {
            decompiler.dispose();
        }
    }

    private Function ensureFunction(Address entry) throws Exception {
        Function function = getFunctionAt(entry);
        if (function != null) {
            return function;
        }
        if (getInstructionAt(entry) == null) {
            disassemble(entry);
        }
        return createFunction(entry, null);
    }

    private void decompileTree(Address entry, int depth) throws Exception {
        if (!done.add(entry)) {
            return;
        }
        Function function = ensureFunction(entry);
        if (function == null) {
            write(entry, "// no function could be created at " + entry + "\n");
            return;
        }

        StringBuilder text = new StringBuilder();
        text.append("// ").append(function.getName()).append(" @ ").append(function.getEntryPoint())
            .append(" body ").append(function.getBody().getMinAddress()).append("..")
            .append(function.getBody().getMaxAddress()).append("\n");

        DecompileResults results = decompiler.decompileFunction(function, 180, monitor);
        if (results.decompileCompleted()) {
            text.append(results.getDecompiledFunction().getC());
        }
        else {
            text.append("// decompile failed: ").append(results.getErrorMessage()).append("\n");
        }

        // Without auto-analysis the function body is just its entry instruction, so callees come
        // from the decompiler's p-code, which follows the real control flow.
        List<Address> callees = new ArrayList<>();
        if (results.decompileCompleted() && results.getHighFunction() != null) {
            Iterator<PcodeOpAST> ops = results.getHighFunction().getPcodeOps();
            while (ops.hasNext()) {
                PcodeOpAST op = ops.next();
                if (op.getOpcode() == PcodeOp.CALL && op.getInput(0).isAddress()) {
                    Address destination = op.getInput(0).getAddress();
                    if (!callees.contains(destination)) {
                        callees.add(destination);
                    }
                }
            }
        }
        text.append("// direct callees: ").append(callees).append("\n");
        write(entry, text.toString());

        if (depth > 0) {
            for (Address callee : callees) {
                decompileTree(callee, depth - 1);
            }
        }
    }

    private void dumpDisassembly(Address start, int count) throws Exception {
        if (getInstructionAt(start) == null) {
            disassemble(start);
        }
        StringBuilder text = new StringBuilder();
        Instruction instruction = getInstructionAt(start);
        for (int i = 0; i < count && instruction != null; i++) {
            text.append(instruction.getAddress()).append("  ").append(instruction).append("\n");
            Instruction next = instruction.getNext();
            if (next == null) {
                Address fallThrough = instruction.getFallThrough();
                if (fallThrough == null) {
                    break;
                }
                disassemble(fallThrough);
                next = getInstructionAt(fallThrough);
            }
            instruction = next;
        }
        write(start, "dis", text.toString());
    }

    private void write(Address address, String content) throws IOException {
        write(address, "c", content);
    }

    private void write(Address address, String extension, String content) throws IOException {
        File file = new File(outDir, address.toString().replace(":", "_") + "." + extension);
        try (FileWriter writer = new FileWriter(file)) {
            writer.write(content);
        }
        println("wrote " + file);
    }
}
