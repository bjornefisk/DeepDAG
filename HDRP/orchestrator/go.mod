module hdrp

go 1.24.0

toolchain go1.24.11

require (
	github.com/deepdag/hdrp/api/gen/services v0.0.0
	github.com/google/uuid v1.6.0
	google.golang.org/grpc v1.78.0
)

require (
	golang.org/x/net v0.47.0 // indirect
	golang.org/x/sys v0.38.0 // indirect
	golang.org/x/text v0.31.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20251029180050-ab9386a59fda // indirect
	google.golang.org/protobuf v1.36.11 // indirect
)

replace github.com/deepdag/hdrp/api/gen/services => ../api/gen/go/HDRP/api/proto
