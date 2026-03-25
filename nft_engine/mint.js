const {
Metaplex,
keypairIdentity,
} = require("@metaplex-foundation/js");

const {
Connection,
clusterApiUrl,
Keypair,
} = require("@solana/web3.js");

const fs = require("fs");

// 🔐 Load your wallet
const secret = JSON.parse(
fs.readFileSync(process.env.HOME + "/.config/solana/id.json")
);

const keypair = Keypair.fromSecretKey(new Uint8Array(secret));

// 🌐 Connect to Solana Devnet
const connection = new Connection(clusterApiUrl("devnet"));

const metaplex = Metaplex.make(connection).use(keypairIdentity(keypair));

(async () => {
try {
console.log("🚀 Minting NFT...");

```
const { nft } = await metaplex.nfts().create({
  uri: "https://arweave.net/YOUR_METADATA_LINK", // temp, will fix later
  name: "SolClub Reward NFT",
  sellerFeeBasisPoints: 0,
});

console.log("✅ NFT Minted Successfully!");
console.log("Mint Address:", nft.address.toBase58());
```

} catch (err) {
console.error("❌ Error:", err);
}
})();
