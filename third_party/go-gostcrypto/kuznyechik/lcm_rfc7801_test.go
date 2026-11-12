// LightCrypto independent expected key schedule values from RFC7801 section5.4.
package kuznyechik
import("encoding/hex";"testing")
func TestLCMRFC7801CTSchedule(t *testing.T){
 key,_:=hex.DecodeString("8899aabbccddeeff0011223344556677fedcba98765432100123456789abcdef")
 expected:=[]string{"8899aabbccddeeff0011223344556677","fedcba98765432100123456789abcdef","db31485315694343228d6aef8cc78c44","3d4553d8e9cfec6815ebadc40a9ffd04","57646468c44a5e28d3e59246f429f1ac","bd079435165c6432b532e82834da581b","51e640757e8745de705727265a0098b1","5a7925017b9fdd3ed72a91a22286f984","bb44e25378c73123a5f32f73cdb6e517","72e9dd7416bcf45b755dbaa88e4a4043"}
 c:=NewCipherCT(key)
 for i,v:=range expected{if hex.EncodeToString(c.ks[i][:])!=v{t.Fatalf("RFC7801 round key %d mismatch",i+1)}}
}
